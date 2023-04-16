import os, concurrent.futures, time, random, re, threading, pymongo
from constant import client, poe_collection, db
from generator import PoeGenerator
from poeapi import poe
from constant import client, poe_collection, db

# # Generate accounts
def run_generation():
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for i in range(10):
            executor.submit(PoeGenerator.generateAccount)

def check_account(account):
    mail, token = account["mail"], account["token"]
    proxy = f"socks5h://{random.randint(0, 99999999)}:foobar@localhost:9150"
    try:
        client = poe.Client(token)
    except:
        token = ""
        tried = 0
        while not token or tried > 3:
            token = PoeGenerator.reverifyAccount(mail)
            tried += 1
        if not token:
            return
        else:
            client = poe.Client(token)
            print(f"\033[31m[*]\033[0m \033[32m Uptated cookie for Mail : {mail}, new is {token} \033[0m")
    
    gpt4_messages = client.get_remaining_messages("GPT-4")
    claudePlus_messages = client.get_remaining_messages("Claude+")

    document = poe_collection.find_one({"mail": mail, "token": token.replace("\n", "").strip()})

    if document:
        document["gpt4"] = gpt4_messages
        document["claude"] = claudePlus_messages

        poe_collection.update_one({"_id": document["_id"]}, {"$set": document})


thread = threading.Thread(target=run_generation)
thread.daemon = True
thread.start()

while True:
    accounts = [account for account in poe_collection.find()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check_account, account) for account in accounts]
        concurrent.futures.wait(futures)
    time.sleep(500)

