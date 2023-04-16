import requests, random, json, re, hashlib, time, logging, concurrent.futures, threading, pymongo
from pathlib import Path
from urllib.parse import urlparse
from account_generator_helper import GmailNator
from constant import client, poe_collection, db

parent_path = Path(__file__).resolve().parent
queries_path = parent_path / "poeapi" / "poe_graphql"
queries = {}
lock = threading.Lock()
logging.basicConfig()
logger = logging.getLogger()

def load_queries():
  for path in queries_path.iterdir():
    if path.suffix != ".graphql":
      continue
    with open(path) as f:
      queries[path.stem] = f.read()
load_queries()

def request_with_retries(method, *args, **kwargs):
    attempts = kwargs.get("attempts") or 2
    url = args[0]
    for i in range(attempts):
        r = method(*args, **kwargs)
        if r.status_code == 200:
            return r
    # raise RuntimeError(f"Failed to download {url} too many times.")

def generate_payload(query_name, variables):
  return {
    "query": queries[query_name],
    "variables": variables
  }


class PoeGenerator:
    gql_url = "https://poe.com/api/gql_POST"
    gql_recv_url = "https://poe.com/api/receive_POST"
    home_url = "https://poe.com"
    settings_url = "https://poe.com/api/settings"
    user_agent = "Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"

    def __init__(self, mail, proxy=None):
        self.proxy = proxy
        self.session = requests.Session()
            
        if proxy:
            self.session.proxies = {
            "http": self.proxy,
            "https": self.proxy
            }

        self.generate_cookies()
        self.headers = {
            "User-Agent": self.user_agent,
            "Referrer": "https://poe.com/",
            "Origin": "https://poe.com",
        }

        self.session.headers.update(self.headers)
        self.next_data = self.get_next_data(overwrite_vars=True)
        self.channel = self.get_channel_data()

        self.gql_headers = {
            "poe-formkey": self.formkey,
            "poe-tchannel": self.channel["channel"],
        }

        self.gql_headers = {**self.gql_headers, **self.headers}

        # account_status = self.requestVerificationCode(mail)
        # code = getMailCode(mail)
        # self.verifyCode(mail, code, account_status)

    def generate_cookies(self):
        self.session.get('https://poe.com/login')

    def get_next_data(self, overwrite_vars=False):

        r = request_with_retries(self.session.get, self.home_url)
        json_regex = r'<script id="__NEXT_DATA__" type="application\/json">(.+?)</script>'
        json_text = re.search(json_regex, r.text).group(1)
        next_data = json.loads(json_text)

        if overwrite_vars:
            self.formkey = self.extract_formkey(r.text)
            self.viewer = next_data["props"]["pageProps"]["payload"]["viewer"]

        return next_data

    
    def get_channel_data(self, channel=None):
        r = request_with_retries(self.session.get, self.settings_url)
        data = r.json()

        return data["tchannelData"]

    def extract_formkey(self, html):
        script_regex = r'<script>if\(.+\)throw new Error;(.+)</script>'
        script_text = re.search(script_regex, html).group(1)
        key_regex = r'var .="([0-9a-f]+)",'
        key_text = re.search(key_regex, script_text).group(1)
        cipher_regex = r'.\[(\d+)\]=.\[(\d+)\]'
        cipher_pairs = re.findall(cipher_regex, script_text)

        formkey_list = [""] * len(cipher_pairs)
        for pair in cipher_pairs:
            formkey_index, key_index = map(int, pair)
            formkey_list[formkey_index] = key_text[key_index]
        formkey = "".join(formkey_list)
        
        return formkey

    def send_query(self, query_name, variables):
        for i in range(20):
            json_data = generate_payload(query_name, variables)
            payload = json.dumps(json_data, separators=(",", ":"))
            base_string = payload + self.gql_headers["poe-formkey"] + "WpuLMiXEKKE98j56k"
            
            headers = {
                "content-type": "application/json",
                "poe-tag-id": hashlib.md5(base_string.encode()).hexdigest()
            }
            headers = {**self.gql_headers, **headers}
            with open("payload.json", "w") as f:
                f.write(payload)
                for header in headers:
                    f.write(f"{header}: {headers[header]}\n")
            r = request_with_retries(self.session.post, self.gql_url, data=payload, headers=headers)
            
            data = r.json()
            if data["data"] == None:
                time.sleep(2)
                continue

            return r.json()
            
        raise RuntimeError(f'{query_name} failed too many times.')
    
    def requestVerificationCode(self, mail):
        message_data = self.send_query("SendVerificationCodeForLoginMutation", {
            "emailAddress": mail,
            "phoneNumber": None,
        })
        # print(message_data)
        if "login" in message_data:
            return message_data['data']['loginWithVerificationCode']['status']
        else:
            return message_data['data']['sendVerificationCode']['status']


    def verifyCode(self, mail, code, status):
        query = "SignupWithVerificationCodeMutation" if status == "user_with_confirmed_email_not_found" else "LoginWithVerificationCodeMutation"
        message_data = self.send_query(query, {
            "verificationCode": code,
            "emailAddress": mail,
            "phoneNumber": None,
        })

        if "success" in str(message_data):
            return mail, self.session.cookies["p-b"]
        else:
            return None, None

    @staticmethod
    def _get_verification_code(mailOject, inbox=None):
        timeElapsed = 0
        code = 0
        while True:
            time.sleep(1)
            timeElapsed += 1
            newInbox = mailOject.get_inbox()
            if inbox is None or len(newInbox) != len(inbox):
                if newInbox and "Poe" in newInbox[0].letter:
                    if len(newInbox[0].letter) > 1000:  # Is html ?
                        pattern = r'text-align:center;color:#333333;">(\d+)</div></td></tr><tr>'
                        code = re.findall(pattern, newInbox[0].letter)[0]
                    else:
                        code = re.findall(r'\d{6}', newInbox[0].letter)[0]
                    break
            if timeElapsed > 15:
                break
        return code

    @staticmethod
    def generateAccount():
        while True:
            try:
                mailOject = GmailNator()
                mail = mailOject.get_email_online(use_plus=False, use_point=False)
                proxy = f"socks5h://{random.randint(0, 99999999)}:foobar@localhost:9150"
                creator = PoeGenerator(mail, proxy=proxy)
                account_status = creator.requestVerificationCode(mail)
                code = PoeGenerator._get_verification_code(mailOject)

                if not code:
                    continue

                mail, cookie = creator.verifyCode(mail, code, account_status)
                if mail and cookie:
                    print(f"\033[31m[+]\033[0m \033[32mMail : {mail} | Code : {code} | Account Type : {account_status}\033[0m")
                    new_document = {"mail": mail, "token": cookie}
                    poe_collection.insert_one(new_document)
            except Exception as e:
                pass

    @staticmethod
    def reverifyAccount(mail):
        mailOject = GmailNator()
        mail = mailOject.set_email(mail)
        inbox = mailOject.get_inbox()
        proxy = f"socks5h://{random.randint(0, 99999999)}:foobar@localhost:9150"
        creator = PoeGenerator(mail, proxy=proxy)
        account_status = creator.requestVerificationCode(mail)
        code = PoeGenerator._get_verification_code(mailOject, inbox)

        mail, cookie = creator.verifyCode(mail, code, account_status)

        return cookie


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for i in range(10):
            executor.submit(PoeGenerator.generateAccount)


