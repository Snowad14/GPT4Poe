from constant import client, poe_collection, db
from flask import Flask, request
from pymongo import MongoClient
from poeapi import poe

app = Flask(__name__)

@app.route('/generate/<string:gpt_type>/<string:prompt>')
def generate(gpt_type, prompt):
    while True:
        if gpt_type == 'claude':
            document = poe_collection.find_one({'claude': {'$lte': 3}})
        elif gpt_type == 'gpt4':
            document = poe_collection.find_one({'gpt4': 1})
        else:
            return "gpt type not found, please use 'claude' or 'gpt4'"
        
        if not prompt:
            return "prompt invalid"

        token = document["token"]
        try:
            client = poe.Client(token)
            client.purge_conversation(gpt_type)
            break
        except:
            poe_collection.update_one({'_id': document['_id']}, {'$set': {gpt_type: 0}})
    print(f"Using mail : {document['mail']}, token : {token}")
    for chunk in client.send_message(gpt_type, prompt):
        pass

    return chunk["text"]


if __name__ == '__main__':
    app.run(debug=True)
