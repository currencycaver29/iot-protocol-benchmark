"""MQTT receiver: subscribes to the broker. Usage: python mqtt_subscriber.py <log.csv>"""
import sys
import paho.mqtt.client as mqtt
from sink import Sink
import config

sink = Sink(sys.argv[1])


def on_connect(c, userdata, flags, rc, props=None):
    c.subscribe("sensors/+/+", qos=1)


def on_subscribe(c, userdata, mid, reason_codes, props=None):
    # Only report READY once the broker has confirmed the subscription (SUBACK);
    # otherwise the first message can be published before the subscription exists.
    print("READY", flush=True)


def on_message(c, userdata, msg):
    sink.record(msg.payload, msg.topic.rsplit("/", 1)[-1])


c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sink")
c.on_connect, c.on_message, c.on_subscribe = on_connect, on_message, on_subscribe
c.connect("127.0.0.1", config.MQTT_PORT)
import socket
c.socket().setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
c.loop_forever()
