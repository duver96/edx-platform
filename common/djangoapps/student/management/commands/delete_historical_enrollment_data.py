"""
Command to delete all rows from the student_historicalcourseenrollment table.
"""

import logging
from django.core.management.base import BaseCommand
from student.models import CourseEnrollment
from openedx.core.djangoapps.util.row_delete import delete_rows, BaseDeletionCommand
log = logging.getLogger(__name__)


class Command(BaseDeletionCommand):
    """
    Example usage: ./manage.py lms --settings=devstack delete_historical_enrollment_data.py
    """
    help = 'Deletes all historical CourseEnrollment rows (in chunks).'

    def handle(self, *args, **options):
        """
        Deletes rows, chunking the deletes to avoid long table/row locks.
        """
        chunk_size, sleep_between = super(Command, self).handle(*args, **options)
        delete_rows(
            CourseEnrollment.objects,
            'student_historicalcourseenrollment',
            chunk_size, sleep_between
        )
