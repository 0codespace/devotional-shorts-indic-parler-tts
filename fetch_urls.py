#!/usr/bin/env python3
"""Fetch background image URLs for each devotional topic from Wikimedia Commons.
Writes image_urls.json keyed BOTH by topic string and by category so render_video.sh
can pick the most relevant image per topic (not just the category default).
Run periodically (or once) to refresh URLs. Safe to re-run.
"""
import json
import time
import urllib.parse
import urllib.request
import os

BASE = os.path.expanduser("~/devotional-shorts")
TOPICS_PATH = os.path.join(BASE, "topics.json")
OUT_PATH = os.path.join(BASE, "image_urls.json")

# Commons file title per topic string (best-effort relevant image)
TOPIC_FILES = {
    "गायत्री मंत्र का अर्थ और महत्व": "File:Rig Veda MS Mandala 3 Wikimedia.jpg",
    "भगवान गणेश को हाथी का सिर कैसे मिला": "File:Rebirth_of_Ganesha.jpg",
    "भगवान शिव के तीसरे नेत्र का रहस्य": "File:Shiva_Third_Eye.jpg",
    "ॐ प्रतीक का आध्यात्मिक महत्व": "File:Om.svg",
    "हनुमान जी द्वारा संजीवनी पर्वत लाने की कथा": "File:Hanuman fetches the herb-bearing mountain, in a print from the Ravi Varma Press, 1910's.jpg",
    "मंदिर में प्रवेश से पहले घंटी क्यों बजाई जाती है": "File: Temple_Bell.jpg",
    "नमस्ते का वास्तविक अर्थ": "File:Namaste.svg",
    "भगवान कृष्ण और गोवर्धन पर्वत की कथा": "File:King_of_Kishangarh.jpg",
    "हिन्दू धर्म में कमल के फूल का महत्व": "File:Nelumbo_nucifera_open_flower.jpg",
    "दीपावली और भगवान राम की अयोध्या वापसी": "File:Rama Returning to Ayodhya.jpg",
    "देवी दुर्गा द्वारा महिषासुर का वध": "File:Durga_by_Raja_Ravi_Varma.jpg",
    "हिन्दू संस्कृति में गाय को पवित्र क्यों माना जाता है": "File:Kamadhenu.jpg",
    "ॐ नमः शिवाय मंत्र का अर्थ": "File:Shiva_meditation.jpg",
    "भगवान विष्णु के दस अवतारों की कथा": "File:Dashavatara.jpg",
    "हर शाम दीपक क्यों जलाया जाता है": "File:Diya.jpg",
    "हिन्दू घरों में तुलसी के पौधे का महत्व": "File:Ocimum_tenuiflorum.jpg",
    "महर्षि वाल्मीकि द्वारा रामायण रचना की कथा": "File:Valmiki.jpg",
    "सूर्य नमस्कार के पीछे का अर्थ": "File:Surya_Namaskar.jpg",
    "देवी सरस्वती ज्ञान की देवी क्यों हैं": "File:Raja Ravi Varma, Goddess Saraswati.jpg",
    "महाभारत में कर्ण के दान की कथा": "File:Karna_in_Mahabharata.jpg",
    "जनेऊ संस्कार का महत्व": "File:Janeu.jpg",
    "मोर पंख का कृष्ण से संबंध": "File:Peacock_with_tail.jpg",
    "दैनिक जीवन में कर्म का अर्थ": "File:Wheel_of_Dharma.svg",
    "शबरी द्वारा भगवान राम की प्रतीक्षा की कथा": "File:Shabari_offering_fruits_to_Rama.jpg",
    "हिन्दू पूजा में 108 अंक का महत्व": "File:108_beads_mala.jpg",
    "हरे कृष्ण मंत्र जाप का महत्व": "File:Hare_Krishna.jpg",
    "ध्रुव की अटूट भक्ति की कथा": "File:Dhruva.jpg",
    "भोजन से पहले भगवान को भोग क्यों लगाया जाता है": "File:Bhog.jpg",
    "आत्मा और शाश्वत जीवन का अर्थ": "File:Atman.svg",
    "मार्कण्डेय की शिव भक्ति की कथा": "File:Markandeya.jpg",
    "गंगा नदी को पवित्र क्यों माना जाता है": "File:Ganges_at_Rishikesh.jpg",
    "नवरात्रि और देवी दुर्गा के नौ रूप": "File:Navratri.jpg",
    "प्रह्लाद की भगवान विष्णु में आस्था की कथा": "File:Prahlada.jpg",
    "दीपक की आरती का महत्व": "File:Aarti.jpg",
    "भगवद गीता में धर्म का अर्थ": "File:Bhagavad_Gita.jpg",
    "सावित्री और सत्यवान की कथा": "File:Savitri_Satyavan.jpg",
    "एकादशी व्रत का महत्व": "File:Ekadashi.jpg",
    "रुद्राक्ष की माला का महत्व": "File:Rudraksha.jpg",
    "भगवान राम के वनवास और वापसी की कथा": "File:Rama_exile.jpg",
    "आध्यात्मिक जीवन में मौन और ध्यान का महत्व": "File:Meditation.jpg",
}

# Category fallback (used if no topic-specific match)
CATEGORY_FILES = {
    "ganesha": "File:Rebirth_of_Ganesha.jpg",
    "shiva": "File:Siva-parvati-by-raja-ravi-varma.jpg",
    "krishna": "File:Yashoda with Krishna, Raja Ravi Varma.jpg",
    "rama": "File:Ramapanchayan, Raja Ravi Varma (Lithograph).jpg",
    "hanuman": "File:Hanuman fetches the herb-bearing mountain, in a print from the Ravi Varma Press, 1910's.jpg",
    "durga": "File:Durga by Raja Ravi Varma.jpg",
    "saraswati": "File:Raja Ravi Varma, Goddess Saraswati.jpg",
    "lakshmi": "File:Raja Ravi Varma, Goddess Lakshmi, 1896.jpg",
    "vishnu": "File:Raja Ravi Varma, Seshanarayana (Oleographic print).jpg",
}

headers = {"User-Agent": "DevotionalShortsBot/2.0 (vijay.looprai@gmail.com)"}
result = {}

def get_url(title):
    url = "https://commons.wikimedia.org/w/api.php?action=query&titles=" + \
          urllib.parse.quote(title) + "&prop=imageinfo&iiprop=url&format=json"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    pages = data["query"]["pages"]
    page = next(iter(pages.values()))
    return page["imageinfo"][0]["url"]

# Load topic pool
topics = json.load(open(TOPICS_PATH))
for t in topics:
    topic_str = t["topic"]
    cat = t["category"]
    title = TOPIC_FILES.get(topic_str) or CATEGORY_FILES.get(cat)
    if not title:
        continue
    try:
        u = get_url(title)
        result[topic_str] = u
        print("topic ->", topic_str[:30], u[:60])
    except Exception as e:
        print("FAIL", topic_str, e)
    time.sleep(1.0)

# Also keep category fallbacks
for cat, title in CATEGORY_FILES.items():
    try:
        result.setdefault(cat, get_url(title))
    except Exception:
        pass

json.dump(result, open(OUT_PATH, "w"), indent=2, ensure_ascii=False)
print("Wrote", len(result), "image entries to", OUT_PATH)
