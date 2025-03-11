from flask import Flask, jsonify, send_from_directory
import csv
import os

app = Flask(__name__, static_folder='dist')  # "dist" hosts your Svelte build

# Build a path to traffic_data.csv in the parent folder
CSV_FILE = os.path.join(os.path.dirname(__file__), '..', 'traffic_data.csv')

def read_incidents():
    incidents = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                incidents.append(row)
    # Sort by timestamp descending so the latest incident comes first
    incidents.sort(key=lambda x: x['Timestamp'], reverse=True)
    return incidents

@app.route('/api/incidents')
def get_incidents():
    return jsonify(read_incidents())

@app.route('/maps/<filename>')
def get_map(filename):
    parent_folder = os.path.join(os.path.dirname(__file__), '..')
    return send_from_directory(parent_folder, filename)

# Serve the Svelte built files
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_app(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(debug=True)
