"""
This file contains celery tasks for sending email
"""
import logging

from boto.exception import NoAuthHandlerFound
from celery.exceptions import MaxRetriesExceededError
from celery.task import task  # pylint: disable=no-name-in-module, import-error
from django.conf import settings
from django.core import mail

log = logging.getLogger('edx.celery.task')


@task(bind=True)
def send_activation_email(self, subject, message, from_address, dest_addr):
    """
    Sending an activation email to the user.
    """
    max_retries = settings.RETRY_ACTIVATION_EMAIL_MAX_ATTEMPTS
    retries = self.request.retries
    try:
        mail.send_mail(subject, message, from_address, [dest_addr], fail_silently=False)
        # Log that the Activation Email has been sent to user without an exception
        log.info("Activation Email has been sent to User {user_email}".format(
            user_email=dest_addr
        ))
    except NoAuthHandlerFound:  # pylint: disable=broad-except
        log.info('Retrying sending email to user {dest_addr}, attempt # {attempt} of {max_attempts}'. format(
            dest_addr=dest_addr,
            attempt=retries,
            max_attempts=max_retries
        ))
        try:
            self.retry(countdown=settings.RETRY_ACTIVATION_EMAIL_TIMEOUT, max_retries=max_retries)
        except MaxRetriesExceededError:
            log.error(
                'Unable to send activation email to user from "%s" to "%s"',
                from_address,
                dest_addr,
                exc_info=True
            )
    except Exception:  # pylint: disable=bare-except
        log.exception(
            'Unable to send activation email to user from "%s" to "%s"',
            from_address,
            dest_addr,
            exc_info=True
        )
        raise Exception


from .signals.signals import ENROLLMENT_TRACK_UPDATED
from django.dispatch import receiver
from email_marketing.models import EmailMarketingConfiguration
from sailthru.sailthru_client import SailthruClient
from sailthru.sailthru_error import SailthruClientError
from student.models import CourseEnrollment
from xmodule.util.django import get_current_request_hostname
from django.core.urlresolvers import reverse


@receiver(ENROLLMENT_TRACK_UPDATED)
def update_sailthru(sender, user, course_key, **kwargs):
    update_course_enrollment.delay(user, course_key)


@task(bind=True)
def update_course_enrollment(self, user, course_key):
    log.info('------------>>> signal is received')

    enrollment = CourseEnrollment.objects.get(user=user, course_id=course_key)
    mode = enrollment.mode
    email = user.email
    course_url = build_course_url(course_key)
    config = EmailMarketingConfiguration.current()

    try:
        sailthru_client = SailthruClient(config.sailthru_key, config.sailthru_secret)
    except:
        return

    new_enroll = False
    send_template = None
    cost_in_cents = None

    if mode == 'audit' or mode == 'honor':
        # free enroll
        new_enroll = True
        send_template = config.sailthru_enroll_template
        cost_in_cents = 0

    if new_enroll:
        if not update_unenrolled_list(sailthru_client, email, course_url, False):
            schedule_retry(self, config)

    course_data = _get_course_content(course_key, course_url, sailthru_client, config)

    item = _build_purchase_item(course_key, course_url, cost_in_cents, mode, course_data, None)

    options = {}

    if send_template:
        options['send_template'] = send_template

    if not _record_purchase(sailthru_client, email, item, options):
        schedule_retry(self, config)

    log.info('-------------->>>>>>>>>>>>>>>>>>>routine completed')


def build_course_url(course_key):
    """
    Generates and return url of the course info page by using course_key
    :param course_key:
    :return:
    """
    return ''.join(['https://', get_current_request_hostname(), reverse('info', kwargs={'course_id': course_key})])


def schedule_retry(self, config):
    """Schedule a retry"""
    raise self.retry(countdown=config.sailthru_retry_interval,
                     max_retries=config.sailthru_max_retries)


def update_unenrolled_list(sailthru_client, email, course_url, unenroll):
    """Maintain a list of courses the user has unenrolled from in the Sailthru user record
    Arguments:
        sailthru_client (object): SailthruClient
        email (str): user's email address
        course_url (str): LMS url for course info page.
        unenroll (boolean): True if unenrolling, False if enrolling
    Returns:
        False if retryable error, else True
    """
    try:
        # get the user 'vars' values from sailthru
        sailthru_response = sailthru_client.api_get("user", {"id": email, "fields": {"vars": 1}})
        if not sailthru_response.is_ok():
            error = sailthru_response.get_error()
            log.error("Error attempting to read user record from Sailthru: %s", error.get_message())
            return not can_retry_sailthru_request(error)

        response_json = sailthru_response.json

        unenroll_list = []
        if response_json and "vars" in response_json and response_json["vars"] \
           and "unenrolled" in response_json["vars"]:
            unenroll_list = response_json["vars"]["unenrolled"]

        changed = False
        # if unenrolling, add course to unenroll list
        if unenroll:
            if course_url not in unenroll_list:
                unenroll_list.append(course_url)
                changed = True

        # if enrolling, remove course from unenroll list
        elif course_url in unenroll_list:
            unenroll_list.remove(course_url)
            changed = True

        if changed:
            # write user record back
            sailthru_response = sailthru_client.api_post(
                'user', {'id': email, 'key': 'email', 'vars': {'unenrolled': unenroll_list}})

            if not sailthru_response.is_ok():
                error = sailthru_response.get_error()
                log.error("Error attempting to update user record in Sailthru: %s", error.get_message())
                return not can_retry_sailthru_request(error)

        return True

    except SailthruClientError as exc:
        log.exception("Exception attempting to update user record for %s in Sailthru - %s", email, unicode(exc))
        return False


def _record_purchase(sailthru_client, email, item, options):
    """Record a purchase in Sailthru
        Arguments:
            sailthru_client (object): SailthruClient
            email (str): user's email address
            item (dict): Sailthru required information about the course
            purchase_incomplete (boolean): True if adding item to shopping cart
            message_id (str): Cookie used to identify marketing campaign
            options (dict): Sailthru purchase API options (e.g. template name)
        Returns:
            False if retryable error, else True
        """
    try:
        sailthru_response = sailthru_client.purchase(email, [item], options=options)

        if not sailthru_response.is_ok():
            error = sailthru_response.get_error()
            log.error("Error attempting to record purchase in Sailthru: %s", error.get_message())
            return not can_retry_sailthru_request(error)
        else:
            log.info('------------>>>> i am here')

    except SailthruClientError as exc:
        log.exception("Exception attempting to record purchase for %s in Sailthru - %s", email, unicode(exc))
        return False

    return True


def can_retry_sailthru_request(error):
    """ Returns True if a Sailthru request and be re-submitted after an error has occurred.
    Responses with the following codes can be retried:
         9: Internal Error
        43: Too many [type] requests this minute to /[endpoint] API
    All other errors are considered failures, that should not be retried. A complete list of error codes is available at
    https://getstarted.sailthru.com/new-for-developers-overview/api/api-response-errors/.
    Args:
        error (SailthruResponseError)
    Returns:
        bool: Indicates if the original request can be retried.
    """
    code = error.get_error_code()
    return code in (9, 43)


def _build_purchase_item(course_id, course_url, cost_in_cents, mode, course_data, sku):
    """Build and return Sailthru purchase item object"""

    # build item description
    item = {
        'id': "{}-{}".format(course_id, mode),
        'url': course_url,
        'price': cost_in_cents,
        'qty': 1,
    }

    # get title from course info if we don't already have it from Sailthru
    if 'title' in course_data:
        item['title'] = course_data['title']
    else:
        # can't find, just invent title
        item['title'] = 'Course {} mode: {}'.format(course_id, mode)

    if 'tags' in course_data:
        item['tags'] = course_data['tags']

    # add vars to item
    item['vars'] = dict(course_data.get('vars', {}), mode=mode, course_run_id=course_id)

    item['vars']['purchase_sku'] = sku

    return item


from .cache import Cache
cache = Cache()


def _get_course_content(course_id, course_url, sailthru_client, config):
    """Get course information using the Sailthru content api or from cache.
        If there is an error, just return with an empty response.
        Arguments:
            course_id (str): course key of the course
            course_url (str): LMS url for course info page.
            sailthru_client (object): SailthruClient
            config (dict): config options
        Returns:
            course information from Sailthru
        """
    # check cache first

    cache_key = "{}:{}".format(course_id, course_url)
    response = cache.get(cache_key)
    if not response:
        try:
            sailthru_response = sailthru_client.api_get("content", {"id": course_url})
            if not sailthru_response.is_ok():
                log.error('Could not get course data from Sailthru on enroll/unenroll event. ')
                response = {}
            else:
                response = sailthru_response.json
                cache.set(cache_key, response, config.sailthru_content_cache_age)

        except SailthruClientError:
            response = {}

    return response
