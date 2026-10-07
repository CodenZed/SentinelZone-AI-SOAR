"""Webhook senders use the same authenticated normalized JSON envelope."""

from app.connectors.generic_rest import GenericRESTConnector


class WebhookConnector(GenericRESTConnector):
    pass
