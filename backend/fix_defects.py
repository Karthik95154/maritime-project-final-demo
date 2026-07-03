import json
from pymongo import MongoClient
c = MongoClient('mongodb://localhost:27017/')
db = c['maritime_inspection2']

defects = list(db.defect_registry.find())
count = 0
for d in defects:
    for sid in d.get('session_ids', []):
        ai_data = db.pipeline_data.find_one({'session_id': sid, 'stage_key': 'repair_ai_json'})
        if ai_data:
            repair_data = ai_data.get('data', {}).get('defect_repairs', {})
            for k, v in repair_data.items():
                if v.get('defect_name') == d.get('defect_type') or True:
                    req_items = v.get('repair_estimation', {}).get('required_items', [])
                    if req_items:
                        line_items = []
                        for it in req_items:
                            line_items.append({
                                'item': it.get('item_name', ''),
                                'description': it.get('item_name', ''),
                                'quantity': it.get('required_quantity', 0),
                                'unit': it.get('metrics', ''),
                                'unit_cost': it.get('unit_cost', 0),
                                'total_cost': it.get('total_cost', 0)
                            })
                        db.defect_registry.update_one({'_id': d['_id']}, {'$set': {'line_items': line_items}})
                        count += 1
                        break
        break

print(f'Updated {count} defects')

