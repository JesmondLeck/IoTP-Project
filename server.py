#Host the server
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_mqtt import Mqtt

#Database
from influxdb import InfluxDBClient
from influxdb.client import InfluxDBClientError

#Visualization
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

#Web Dashboard Setup
import dash
from dash import Dash, html, dcc, ctx
from werkzeug.serving import run_simple
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import dash_daq as daq

import RPi.GPIO as GPIO

#influxdb connection
USER=''
PASSWORD=''
DBNAME='testing'
HOST='localhost'
PORT=8086
dbclient=None;

#display purpose
formatted_time = []

#GPIO setup
fan = 16
buzzer = 26
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(fan,GPIO.OUT)
GPIO.setup(buzzer, GPIO.OUT)
p = GPIO.PWM(fan,50)

#Used to displayed data in the dashboard
numbers=[]
dt = []
df = None

#Control fan activation and speed
speed_display=0
#speed = 0
THRESHOLD = 28

app = Flask(__name__)

#App configuration
app.config['MQTT_BROKER_URL'] = 'test.mosquitto.org'
app.config['MQTT_BROKER_PORT'] = 1883
app.config['MQTT_USERNAME'] = ''
app.config['MQTT_PASSWORD'] = ''
app.config['MQTT_KEEPALIVE'] = 5
app.config['MQTT_TLS_ENABLED'] = False

#same topic as publisher
topic = 'sensor_data'

#create a mqtt client to receive data from the mqtt publisher
mqtt_client = Mqtt(app)

#create a dash app to visualize data received into the web with the usage of graphs created from plotly
dashboard = Dash(__name__, 
		server = app, 
		url_base_pathname = '/',
		external_stylesheets = [dbc.themes.BOOTSTRAP])

dashboard.layout = html.Div([dbc.Container([
		      	     html.Div(id = "placeholder"),
			     html.Div(id = "placeholder2"),
			     html.H1('IoT Monitoring Smart Aquaponics'),
			     html.Br(),
			     dbc.Row([
				dbc.Col(
					dbc.Card([
                       			         html.Div(id='update-text-dynamic'),
                       			         html.Br(),
                                		 html.Div([
                                        	 dbc.Label("Reading to display:"),
                                       		 dbc.RadioItems(
                                                	options=[
                                                        	{"label": "Temperature", "value": "Temperature"},
                                                        	{"label": "Humidity", "value": "Humidity"},
                                                	],
                                                	value = "Temperature",
                                                	id='sensor_reading',
                                        	),
                                		]),
						html.H3("Control Fan", className = "mt-3"),
						html.Div(
						      [
							dbc.Button("Activate Fan", 
						     		   id = "btn-activate", 
							   	   outline = True, 
							  	   color = "primary",
								   size = "lg",
							   	   className = "me-1"),
							dbc.Button("Deactivate Fan",
								   id = "btn-deactivate",
							   	   outline = True,
							           color = "danger",
								   size = "lg",
							   	   className = "me-1")
						     ],
						     className = "mt-2 d-flex justify-content-start"
						),
						html.H3("Fan Speed (From 0 to 100)", className = "mt-3"),
						html.Div(
						      [
							dbc.Button('-',
								   id = "btn-decrease",
								   outline = True,
								   color = "warning",
								   size = "lg",
								   className = "me-1"),
							html.Div(id="btn-pwm-text", className = "pt-2"),
							dbc.Button('+',
								   id = "btn-increase",
								   outline = True,
								   color = "success",
								   size = "lg",
								   className = "me-1")
						     ],
						     className = "mt-2 d-flex justify-content-between"
						),
						html.H3("Threshold Set To Auto Turn On Fan", className = "mt-3"),
						html.Div([
							dcc.Input(id='threshold_value',value=f"{THRESHOLD}",type='text'),
							dbc.Button("Set", 
								   id='threshold_submit_btn',
								   outline = True,
								   color = "danger",
								   size = "md",
								   className = "ms-1")
						],
						className = "mt-2 d-flex justify-content-start"),
					], style = {"fontSize": "20px"})
				, md = 4),
				dbc.Col([
					dcc.Graph(id = "update-graph-dynamic"),
					html.Div(id="gauge-meter", children = "")
					], md = 8),
			], align = "center",)
		], fluid = True, ),
		dcc.Interval(
			     id = 'refresh-readings-dashboard-speed',
			     interval = 2000,
			     n_intervals = 0),
		dcc.Interval(
			     id = "fan-update-speed",
			     interval = 500,
			     n_intervals = 0)
	])

#establish connection 
@mqtt_client.on_connect()
def handle_connect(client, userdata, flags, rc):
	if rc == 0:
		#subscribe only when is successful
		print('Successful connection')
		mqtt_client.subscribe(topic)
	else:
		print('Error due to bad connection. Code:', rc)

#receiven data via MQTT
@mqtt_client.on_message()
def handle_mqtt_message(client, userdata, message):
	data = dict(
		topic = message.topic,
		payload = message.payload.decode()
	)
	#check which data is being received
	print('Received message on {topic} with {payload}'.format(**data))

	#to store time, temperature, and humidity messages
	storage = data['payload'].split('\n')

	#to get time, temperature, and humidity values with their texts
	sensor_readings = [storage[x].split(':', 1) for x in range(len(storage)) if x > 0]
	pointValues = [
		{
			'time': sensor_readings[0][1],
			'measurement': 'reading',
			'tags': {
				'temp': sensor_readings[1][0],
				'humi': sensor_readings[2][0]
			},
			'fields':{
				'temp': float(sensor_readings[1][1]),
				'humi': float(sensor_readings[2][1])
			}
		}
	]

	#establish connection with InfluxDB database
	dbclient = InfluxDBClient(HOST,PORT,USER,PASSWORD,DBNAME)
	#write the data to the database
	dbclient.write_points(pointValues)

def getValue():
	global df
	#establish connection with InfLuxDB database
	dbclient = InfluxDBClient(HOST,PORT,USER,PASSWORD,DBNAME)
	query = 'SELECT * FROM reading'

	#get all the time, temperature and humidity data
	datas = dbclient.query(query)
	sensor_value = list(datas.get_points())
	
	#store all data into a pandas DataFrame object
	df = pd.DataFrame.from_dict(sensor_value)
	
	#get the latest time value
	displayed_time = sensor_value[-1]['time']

	#format the latest time value to be shown in the web dashboard
	formatted_time.append(displayed_time[:10]+' '+displayed_time[11:19])
	return df

@dashboard.callback(
	Output("placeholder", "children"),
	Input('btn-increase','n_clicks'),
	Input('btn-decrease','n_clicks'),
	Input('btn-activate','n_clicks'),
	Input('btn-deactivate','n_clicks')
)
def controlPwm(btn_increase, btn_decrease, btn_activate, btn_deactivate):
	global speed_display,speed

	if 'btn-activate' == ctx.triggered_id:
		speed_display=100
		speed=100
		p.start(speed)
		return html.Div("")
	
	elif 'btn-deactivate' == ctx.triggered_id:
		speed_display = 0
		speed=0
		p.start(speed)
		return html.Div("")

	elif 'btn-increase' == ctx.triggered_id:
		if (speed == 0):
			speed = 50
		elif (speed < 95):
			speed+=5
		speed_display+=10
		p.ChangeDutyCycle(speed)
		return html.Div("")

	elif 'btn-decrease' == ctx.triggered_id:
		if (speed > 0 or speed_display>0):
			speed-=5
			speed_display-=10
			p.ChangeDutyCycle(speed)
			return html.Div("")

	return dash.no_update

@dashboard.callback(
	Output('update-graph-dynamic', 'figure'),
	Input('sensor_reading', 'value'),
        Input('refresh-readings-dashboard-speed', 'n_intervals')
)
def render_dashboard(reading, n):
	#display temperature or humidity readings depending on which radio button is chosen
	if reading == 'Temperature':
		#convert temp column of DataFrame into float to ensure correct display of Dashboard data
		y = df['temp'].astype("float32")
		y_text = "Temperature"
	elif reading == "Humidity":
		#convert humi column of DataFrame into float to ensure correct display of Dashboard data
		y = df['humi'].astype("float32")
		y_text = "Humidity"

	#only display if values can be found in the database
	if not isinstance(df, type(None)):
		fig = go.Figure(go.Scatter(x = df['time'], y = y))
		fig.update_layout(
			autotypenumbers = "convert types",
			title_text = f"Time vs {y_text}",
			title_x = 0.5,
    			xaxis_title = "Time",
    			yaxis_title = f"{y_text}",
		)
		fig.update_yaxes(showticklabels = False)
		fig.update_xaxes(rangeslider_visible = True)
	return fig

@dashboard.callback(
	Output('update-text-dynamic', 'children'),
	Input('refresh-readings-dashboard-speed', 'n_intervals')
)
def update_metrics(n):
	temp = float(getValue()['temp'].to_list()[-1])
	humi = float(getValue()['humi'].to_list()[-1])
	time = formatted_time[-1]
	style={'fontSize':'20px', "marginBottom": '5px'}
	return[
		html.Div([
			dbc.Label("Time:"),
			html.Br(),
			html.Span(f'{time}')
			], style = style),
		html.Div([
			dbc.Label("Temperature:"),
			html.Br(),
			html.Span(f'{temp:.2f}')
			], style = style),
		html.Div([
			dbc.Label("Humidity:"),
			html.Br(),
			html.Span(f'{humi:.2f}')
			], style = style)
	]

@dashboard.callback(
	Output("gauge-meter","children"),
	Input('sensor_reading', 'value'),
	Input("refresh-readings-dashboard-speed","n_intervals")
)
def update_gauge(reading,n):
	#display temperature or humidity readings depending on which radio button is chosen
	if reading == 'Temperature':
		gauge_val=df['temp'].iloc[-1]
		units='°C'
	elif reading == "Humidity":
		gauge_val=df['humi'].iloc[-1]
		units='%'
	fig=go.Figure(go.Indicator(
		mode='gauge+number',
		value=gauge_val,
		number={'valueformat':'.2f','suffix':units},
		title={'text':reading}))
	
	return html.Div([
		    dcc.Graph(figure=fig)
		])

@dashboard.callback(
	Output("btn-pwm-text", "children"),
	Input("fan-update-speed", "n_intervals")
)
def auto_fan(n):
	global speed,speed_display
	#get latest temperature reading
	temp = float(getValue()["temp"].to_list()[-1])

	#if is above threshold set, activate the fan and turn on the buzzer
	if temp > THRESHOLD:
		GPIO.output(buzzer, 1)
		speed_display=100
		speed = 100
		p.start(speed)

	#when is below threshold set, turn off the buzzer
	else:
		GPIO.output(buzzer, 0)

	fan_speed = f"{speed_display}"
	return html.Div(fan_speed)

@dashboard.callback(
	Output("placeholder2","children"),
	Input("threshold_submit_btn","n_clicks"),
	State("threshold_value","value")
)
def update_threshold(threshold_submit,threshold_value):
	global THRESHOLD
	if threshold_submit is not None:
		THRESHOLD=float(threshold_value)

if __name__=='__main__':
	run_simple('0.0.0.0', 5000, app,use_reloader = True, use_debugger = True)

