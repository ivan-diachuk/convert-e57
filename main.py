import os
import requests
from dotenv import load_dotenv
import zipfile
import shutil
from unpack import unpack
from submit import submit
import logging
import sys

load_dotenv()

logging.basicConfig(level=logging.INFO)

def fetch_matterport_assets(auth_key, matter_id):
    """
    Fetches assets from the Matterport API.

    param auth_key: The API authentication key.
    param query: The GraphQL query string.
    return: The first asset URL.
    raises ValueError: If no asset URL is found.
    """

    url = "https://api.matterport.com/api/mp/models/graph"
    headers = {
        "Authorization": f"Bearer {auth_key}",
        "Content-Type": "application/json"
    }
    query = f"""
        query Model {{
            model(id: "{matter_id}") {{
                bundle(id: "mp:e57") {{
                    availability
                    assets {{
                        url
                    }}
                }}
            }}
        }}
    """
    payload = {"query": query}

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        # Extract the URL from the assets
        assets = data.get("data", {}).get("model", {}).get("bundle", {}).get("assets", [])
        if not assets:
            raise ValueError("No assets found in the response.")

        asset_url = assets[0].get("url")  # Assuming you want the first URL
        if not asset_url:
            raise ValueError("Asset URL not found in the assets.")

        return asset_url

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Error fetching assets: {e}")


def download_file(url, output_file):
    """
    Downloads a file from the given URL and saves it with the specified name.

    param url: The URL to download the file from.
    param output_file: The name of the file to save the downloaded content.
    return: None
    """
    try:
        logging.info(f"Downloading from {url}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an error for HTTP status codes >= 400

        # Save the content to a file
        with open(output_file, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        logging.info(f"File saved as {output_file}.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Error downloading the file: {e}")


def unzip_file(zip_path, extract_to):
    """
    Unzips the specified zip file to a given directory and deletes the zip file afterward.

    param zip_path: Path to the zip file.
    param extract_to: Directory where the zip file will be extracted.
    return: None
    """
    try:
        logging.info(f"Unzipping {zip_path} to {extract_to}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        logging.info(f"Unzipped files to {extract_to}.")
    except zipfile.BadZipFile as e:
        raise RuntimeError(f"Error unzipping file: {e}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            logging.info(f"Deleted zip file: {zip_path}")


def rename_and_move_files(source_dir, target_dir):
    """
    Renames and moves `.e57` files from the source directory to the target directory.

    param source_dir: The directory containing the extracted files.
    param target_dir: The directory to move and rename files into.
    return: None
    """
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)  # Create the target directory if it doesn't exist

    files = sorted([f for f in os.listdir(source_dir) if f.endswith(".e57")])
    for index, file_name in enumerate(files):
        old_path = os.path.join(source_dir, file_name)
        new_name = f"treedis_{index}.e57"
        new_path = os.path.join(target_dir, new_name)

        logging.info(f"Renaming {old_path} to {new_path}...")
        os.rename(old_path, new_path)

    # Remove the source directory after files are moved
    logging.info(f"Removing source directory: {source_dir}...")
    shutil.rmtree(source_dir)
    logging.info(f"All files have been renamed and moved to {target_dir}.")


def run_unpack_script():
    scans_folder = "./scans"

    try:
        if not os.path.exists(scans_folder):
            raise RuntimeError(f"The folder '{scans_folder}' does not exist.")

        for file_name in os.listdir(scans_folder):
            file_path = os.path.join(scans_folder, file_name)

            if os.path.isfile(file_path):
                try:
                    unpack(file_path)
                    os.remove(file_path)
                except Exception as e:
                    logging.error(f"Error unpacking file '{file_name}': {e}")
                    continue

        logging.info("Unpack script completed.")

    except Exception as e:
        raise RuntimeError(f"An error occurred during unpacking: {e}")


def run_submit_script():
    scans_folder = "./scans"

    try:
        if not os.path.exists(scans_folder):
            raise RuntimeError(f"The folder '{scans_folder}' does not exist.")

        for item in os.listdir(scans_folder):
            folder_path = os.path.join(scans_folder, item)

            if os.path.isdir(folder_path) and item.endswith("-out"):
                name = item.split("-out")[0]

                try:
                    submit(name)
                except Exception as e:
                    logging.error(f"Error submitting {name}: {e}")

        shutil.rmtree(scans_folder)
        logging.info("Submit script completed.")

    except Exception as e:
        raise RuntimeError(f"An error occurred during submission: {e}")


def main():
    auth_key = os.getenv("MATTERPORT_OAUTH_TOKEN")
    matter_id = os.getenv("MATTERPORT_ID")

    if not auth_key or not matter_id:
        raise EnvironmentError(
            "Missing required environment variables: MATTERPORT_OAUTH_TOKEN and MATTERPORT_ID."
        )

    output_file = "treedis.zip"
    extract_to = "tmp_scans"
    scans_dir = "scans"

    try:
        asset_url = fetch_matterport_assets(auth_key, matter_id)
        download_file(asset_url, output_file)
        unzip_file(output_file, extract_to)
        rename_and_move_files(extract_to, scans_dir)
        run_unpack_script()
        run_submit_script()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Program terminated with an error: {e}", exc_info=True)
        sys.exit(1)
