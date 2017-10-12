"""
Command to delete all rows from the credit_historicalcreditrequest and
credit_historicalcreditrequirementstatus tables.
"""

import logging
from django.core.management.base import BaseCommand
from openedx.core.djangoapps.credit.models import CreditRequest, CreditRequirementStatus
from openedx.core.djangoapps.util.row_delete import delete_rows
log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Example usage: ./manage.py lms --settings=devstack delete_historical_credit_data.py
    """
    help = 'Deletes all historical CreditRequest and CreditRequirementStatus rows (in chunks).'

    def handle(self, *args, **options):
        """
        Deletes rows, chunking the deletes to avoid long table/row locks.
        """
        chunk_size, sleep_between = super(Command, self).handle(*args, **options)
        delete_rows(
            CreditRequest.objects,
            'credit_historicalcreditrequest',
            chunk_size, sleep_between
        )
        delete_rows(
            CreditRequirementStatus.objects,
            'credit_historicalcreditrequirementstatus',
            chunk_size, sleep_between
        )
