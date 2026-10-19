import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Ruta al archivo de credenciales descargado de Google Cloud Console
CREDENTIALS_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def main():
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=5000)
    print('Access Token:', creds.token)
    print('Refresh Token:', creds.refresh_token)
    print('Client ID:', creds.client_id)
    print('Client Secret:', creds.client_secret)

if __name__ == '__main__':
    main()
