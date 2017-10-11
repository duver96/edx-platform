"""
Tests for Video Pipeline api utils.
"""
import ddt
import mock
from mock import Mock

from django.test.testcases import TestCase

from student.tests.factories import UserFactory

from openedx.core.djangoapps.video_pipeline.api import update_3rd_party_transcription_service_credentials
from openedx.core.djangoapps.video_pipeline.tests.mixins import VideoPipelineIntegrationMixin


@ddt.ddt
class TestAPIUtils(VideoPipelineIntegrationMixin, TestCase):
    """
    Tests for API Utils.
    """
    def setUp(self):
        self.pipeline_integration = self.create_video_pipeline_integration()
        self.user = UserFactory(username=self.pipeline_integration.service_username)

    def test_update_service_credentials_with_integration_disabled(self):
        """
        Test updating the credentials when service integration is disabled.
        """
        self.pipeline_integration.enabled = False
        self.pipeline_integration.save()
        is_updated, response_content = update_3rd_party_transcription_service_credentials()
        self.assertEqual((is_updated, response_content), (False, ''))

    def test_update_service_credentials_with_unknown_user(self):
        """
        Test updating the credentials when expected service user is not registered.
        """
        self.pipeline_integration.service_username = 'non_existent_user'
        self.pipeline_integration.save()
        is_updated, response_content = update_3rd_party_transcription_service_credentials()
        self.assertEqual((is_updated, response_content), (False, ''))

    @ddt.data(
        (
            {
                'invalid_param': 'invalid_value'
            },
            Mock(status_code=400, content='Your credentials update was a failure')
        ),
        (
            {
                'username': 'Jason_cielo_24',
                'api_key': '12345678',
            },
            Mock(status_code=200, content='Your credentials were successfully updated.')
        ),
        (
            {
                'api_key': '12345678',
                'api_secret': '11111111',
            },
            Mock(status_code=200, content='Your credentials were successfully updated.')
        ),
    )
    @ddt.unpack
    @mock.patch('openedx.core.djangoapps.video_pipeline.utils.EdxRestApiClient')
    def test_update_service_credentials(self, credentials_payload, pipeline_response, mock_client):
        """
        Tests that the update service credentials util works as expected.
        """
        # Mock update request to edx-video-pipeline.
        mock_update_credentials = Mock(return_value=pipeline_response)
        mock_client.return_value.transcript_credentials.post = mock_update_credentials
        # try updating the transcript service credentials
        is_updated, message = update_3rd_party_transcription_service_credentials(**credentials_payload)
        mock_update_credentials.assert_called_with(credentials_payload)
        self.assertEqual(is_updated, pipeline_response.status_code == 200)
        self.assertEqual(message, pipeline_response.content)
