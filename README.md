## Config

To access Google Sheets API Google Service Account is required:
https://developers.google.com/android/management/service-account

After creating Service Account go to "Keys" and generate new Json key.

Put it to app/config/google-service-account-key.json.

Then enable Google Sheets API for it.

## DEV

### Install dependencies
pipenv install --dev

### Setup pre-commit and pre-push hooks
pipenv run pre-commit install -t pre-commit
pipenv run pre-commit install -t pre-push
