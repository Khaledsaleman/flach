import unittest
import json
from app import app

class BackendTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_events_endpoint(self):
        # Trigger an event
        response = self.app.post('/trigger-event',
                                 data=json.dumps({"user_id": "test_user", "type": "bonus_gold", "payload": {"amount": 500}}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)

        # Retrieve the event
        response = self.app.get('/events?user_id=test_user')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['events']), 1)
        self.assertEqual(data['events'][0]['type'], 'bonus_gold')
        self.assertEqual(data['events'][0]['payload']['amount'], 500)

    def test_notify_endpoint_missing_params(self):
        response = self.app.post('/notify',
                                 data=json.dumps({"message": "hello"}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)

if __name__ == '__main__':
    unittest.main()
