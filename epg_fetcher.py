import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
from datetime import datetime, timedelta
import pytz
from gzip import open as gzip_open

# Channel URLs (update as needed)
channel_urls = {
    "cg_hbohd": "http://www.hbo.com",
    # Add more channel mappings here
}

def fetch_epg():
    now_utc = datetime.utcnow()
    start_time = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_time = (now_utc + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')

    url = "https://live-data-store-cdn.api.pldt.firstlight.ai/content/epg"
    params = {
        "start": start_time,
        "end": end_time,
        "reg": "ph",
        "dt": "all",
        "client": "pldt-cignal-web",
        "pageNumber": 1,
        "pageSize": 100,
    }

    headers = {
        'User-Agent': 'Mozilla/5.0',
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        print("📡 Raw API Response received.")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching EPG: {e}")
        return []

def create_epg_xml(epg_data):
    if isinstance(epg_data, dict) and 'data' in epg_data:
        epg_data = epg_data['data']
    else:
        print("❌ Incorrect EPG data format.")
        return

    tv = ET.Element('tv', {'generator-info-name': 'none', 'generator-info-url': 'none'})
    programs_by_channel = {}
    added_count = 0
    skipped_count = 0

    for item in epg_data:
        if 'airing' not in item:
            continue

        for airing in item['airing']:
            channel_details = airing['ch']
            channel_id = channel_details.get('cs', 'unknown')
            display_name = channel_details.get('ex_id', 'Unknown Channel')

            if channel_id not in programs_by_channel:
                programs_by_channel[channel_id] = []

                channel_elem = ET.SubElement(tv, 'channel', {'id': channel_id})
                ET.SubElement(channel_elem, 'display-name', {'lang': 'en'}).text = display_name
                url = channel_urls.get(channel_id, "http://example.com")
                ET.SubElement(channel_elem, 'url').text = url

            # Validate & parse time
            try:
                st_raw = airing.get('st', '')
                et_raw = airing.get('et', '')

                if not (st_raw.endswith("Z") and et_raw.endswith("Z")):
                    raise ValueError(f"Invalid time format: st={st_raw}, et={et_raw}")

                start_utc = datetime.strptime(st_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
                end_utc = datetime.strptime(et_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
            except Exception as e:
                print(f"❌ Skipping program due to time parsing error: {e}")
                skipped_count += 1
                continue

            manila_tz = pytz.timezone('Asia/Manila')
            start_manila = start_utc.astimezone(manila_tz)
            end_manila = end_utc.astimezone(manila_tz)

            start_str = start_manila.strftime('%Y%m%d%H%M%S') + " +0800"
            end_str = end_manila.strftime('%Y%m%d%H%M%S') + " +0800"

            title = airing['pgm']['lon'][0]['n'] if airing['pgm'].get('lon') else 'No Title'
            description = airing['pgm']['lod'][0]['n'] if airing['pgm'].get('lod') else 'No Description'

            programme = ET.SubElement(tv, 'programme', {
                'start': start_str,
                'stop': end_str,
                'channel': channel_id
            })

            ET.SubElement(programme, 'title', {'lang': 'en'}).text = title
            ET.SubElement(programme, 'desc', {'lang': 'en'}).text = description
            added_count += 1

    try:
        xml_str = ET.tostring(tv, encoding="utf-8", method="xml").decode()
        parsed_xml = minidom.parseString(xml_str)

        save_path = os.path.join(os.getcwd(), "cignal_epg.xml")
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(parsed_xml.toprettyxml(indent="  "))
        print(f"✅ EPG saved to {save_path}")

        # Save GZIP version
        gz_path = save_path + ".gz"
        with gzip_open(gz_path, "wt", encoding="utf-8") as gz:
            gz.write(parsed_xml.toprettyxml(indent="  "))
        print(f"✅ GZipped EPG saved to {gz_path}")

        # Summary
        print(f"📊 {added_count} programs added, ❌ {skipped_count} skipped due to bad timestamps.")

    except Exception as e:
        print(f"❌ Error saving XML: {e}")

def main():
    print("🚀 Starting EPG generation...")
    epg_data = fetch_epg()

    if not epg_data:
        print("❌ No EPG data received.")
    else:
        print("📥 EPG data fetched, generating XML...")
        create_epg_xml(epg_data)

if __name__ == "__main__":
    main()
