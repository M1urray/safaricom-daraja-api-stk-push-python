import qrcode
from flask import Flask, render_template, request, jsonify, redirect, url_for
import requests, datetime, base64
from twilio.rest import Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)

@app.route('/payment', methods=['GET'])
def payment_page():
    return render_template('payment.html')

@app.route('/process_payment', methods=['POST'])
def process_payment():
    phone_number = request.form['phone_number']
    amount = 2500  # Amount from the service details
    service_id = request.form['service_id']

    # Call the M-Pesa STK Push API
    payment_response = initiate_stk_push(phone_number,amount)

    if payment_response['status'] == 'success':
        # Redirect to the callback page for confirmation
        return redirect(url_for('payment_confirmation', service_id=service_id, phone_number=phone_number))
    else:
        return jsonify({'message': 'Payment initiation failed.', 'error': payment_response['error']}), 400

@app.route('/payment_confirmation', methods=['GET', 'POST'])
def payment_confirmation():
    if request.method == 'POST':
        service_id = request.form['service_id']
        phone_number = request.form['phone_number']

        # Call the M-Pesa API to check payment status
        payment_status = check_payment_status(service_id, phone_number)
        if payment_status['status'] == 'success':
            # Send SMS and email notifications
            send_confirmation_sms(phone_number)
            send_confirmation_email(phone_number)
            return jsonify({'message': 'Payment confirmed and notifications sent.'}), 200
        else:
            return jsonify({'message': 'Payment confirmation failed.', 'error': payment_status['error']}), 400

    service_id = request.args.get('service_id')
    phone_number = request.args.get('phone_number')
    return render_template('confirm_payment.html', service_id=service_id, phone_number=phone_number)

def initiate_stk_push(phone_number,amount):
    consumer_key = 'refXH8h0SHesas1jTPb8efLArZHMFopGk2DM1rMg36h1G9Q4'
    consumer_secret = 'wwGuKAsdb3fUYFwFdtlSU0VLSbDfKtnxyQMBu1Rt0IGFHPnWYlRQ5j0h0xIbVGFJ'
    shortcode = '174379'
    passkey = 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919'

    # Generate access token
    auth_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    auth_response = requests.get(auth_url, auth=(consumer_key, consumer_secret))
    access_token = auth_response.json().get('access_token')

    # Prepare STK push payload
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode((shortcode + passkey + timestamp).encode()).decode()

    stk_url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": "https://your_callback_url.com/mpesa/callback",
        "AccountReference": "Exuburn",
        "TransactionDesc": "Payment for service"
    }

    response = requests.post(stk_url, json=payload, headers=headers)
    if response.status_code == 200:
        return {"status": "success", "response": response.json()}
    else:
        return {"status": "error", "error": response.json()}

def check_payment_status(service_id, phone_number):
    # Query the payment status (you would typically implement this using M-Pesa APIs or database verification)
    # Simulating a successful status here
    return {"status": "success"}

def send_confirmation_sms(phone_number):
    account_sid = 'YOUR_TWILIO_SID'
    auth_token = 'YOUR_TWILIO_AUTH_TOKEN'
    client = Client(account_sid, auth_token)

    message = client.messages.create(
        body="Your payment was successful. Thank you for using our service.",
        from_='+1234567890',  # Replace with your Twilio number
        to=phone_number
    )
    return message.sid

def send_confirmation_email(phone_number):
    sender_email = "your_email@example.com"
    receiver_email = "user_email@example.com"  # Update with the user's email
    password = "YOUR_EMAIL_PASSWORD"

    subject = "Payment Confirmation"
    body = f"Dear User,\n\nYour payment linked to phone number {phone_number} was successful. Thank you for using our service."

    # Email configuration
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    # Connect and send the email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())

@app.route('/mpesa/callback', methods=['POST'])
def mpesa_callback():
    data = request.json

    # Process the callback response
    result_code = data['Body']['stkCallback']['ResultCode']
    if result_code == 0:
        # Successful payment
        phone_number = data['Body']['stkCallback']['CallbackMetadata']['Item'][4]['Value']
        send_confirmation_sms(phone_number)
        return jsonify({'message': 'Payment successful'}), 200
    else:
        # Payment failed
        return jsonify({'message': 'Payment failed'}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
