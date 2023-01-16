import paho.mqtt.client as mqtt
import time
import psutil
import smbus2
import bme280

mqtt_broker = "test.mosquitto.org"
topic = "sensor_data"

port=1
address=0x76
bus=smbus2.SMBus(port)

calibration_params=bme280.load_calibration_params(bus,address)

while True:
    data = bme280.sample(bus,address,calibration_params)
    payload = f'\nTimestamp:{data.timestamp} \nTemperature:{data.temperature} \nHumidity:{data.humidity}'
    my_mqtt = mqtt.Client()
    my_mqtt.connect(mqtt_broker, port=1883)
    print("\n--connected to broker")

    try:
        my_mqtt.publish(topic, payload)
        print(f'\nTimestamp:{data.timestamp} \nTemperature:{data.temperature} \nHumidity:{data.humidity}')
    except Exception as e:
        print(e)
        print("--error publishing!")
    else:
        my_mqtt.disconnect()
        print("--disconnected from broker")

    time.sleep(2)
