import sqlite3
import requests
import time
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

users_file = "users.db"

while True:

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users_new')
    users = c.fetchall()
    for user in users:
        _, osu_username, rank, bws_rank, country, last_updated, badges = user

        update_date = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")
        time_diff = datetime.now() - update_date

        if not time_diff > timedelta(hours=1):
            print(f"Skipping {osu_username} because already updated less than a day ago.")
            continue

        r = requests.get(f"https://osu.ppy.sh/users/{osu_username}/osu")

        soup = BeautifulSoup(r.text, 'html.parser')
        try:
            json_user = soup.find(id="json-user").string
            json_achievements = soup.find(id="json-achievements").string
        except:
            continue
        user_dict = json.loads(json_user)
        new_rank = user_dict["statistics"]["pp_rank"]
        if badges == -1:
            new_badges = len(user_dict["badges"])
        else:
            new_badges = badges

        last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bws_rank = max(1, int(pow(new_rank, (pow(0.9937, pow(new_badges, 2))))))

        c.execute("UPDATE users_new SET rank=?, bws_rank=?, last_updated=?, badges=? WHERE osu=?",
                  (new_rank, bws_rank, last_updated, new_badges, osu_username))
        conn.commit()

        print(f"Successfully updated {osu_username}!")
        break
    conn.close()
    time.sleep(150)
