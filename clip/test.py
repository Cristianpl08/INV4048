import requests

def list_projects(api_key):
    url = "https://api.abacus.ai/api/v0/listProjects"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {str(e)}")

# Reemplaza con tu API key
api_key = "YOUR_API_KEY"
list_projects(api_key)