import os
import requests
from dotenv import load_dotenv
import zipfile
import shutil
from unpack import unpack
from submit import submit
import logging
import sys
import boto3
from pathlib import Path

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

ROOT_DIR = '/app/data'

def fetch_matterport_assets(auth_key, matter_id, bundle_id):
    """
    Fetches assets from the Matterport API.
    """
    url = "https://api.matterport.com/api/mp/models/graph"
    headers = {
        "Authorization": f"Bearer {auth_key}",
        "Content-Type": "application/json",
    }
    query = f"""
        query Model {{
            model(id: "{matter_id}") {{
                bundle(id: "{bundle_id}") {{
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
        bundle = data.get("data", {}).get("model", {}).get("bundle", {})
        assets = bundle.get("assets", [])
        if not assets or not assets[0].get("url"):
            raise ValueError("No valid asset URL found in the response.")

        logging.info("Bundle availability: %s", bundle["availability"])
        logging.info("Returning asset URL: %s", assets[0]["url"])

        return assets[0]["url"]

    except requests.exceptions.RequestException as e:
        logging.error("Failed to fetch Matterport assets", exc_info=True)
        raise RuntimeError(f"Error fetching assets from Matterport: {e}") from e


def download_file(url, output_file):
    """
    Downloads a file from the given URL.
    """
    try:
        logging.info(f"Starting download from {url}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(output_file, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        logging.info(f"File successfully downloaded as {output_file}.")

    except requests.exceptions.RequestException as e:
        logging.error("File download failed", exc_info=True)
        raise RuntimeError(f"Error downloading the file from {url}: {e}") from e


def unzip_file(zip_path, extract_to):
    """
    Unzips a file and removes the zip file afterward.
    """
    try:
        logging.info(f"Extracting {zip_path} to {extract_to}...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_to)
        logging.info(f"Extraction completed to {extract_to}.")

    except zipfile.BadZipFile as e:
        logging.error("Failed to unzip file", exc_info=True)
        raise RuntimeError(f"Error unzipping the file {zip_path}: {e}") from e

    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            logging.info(f"Deleted zip file: {zip_path}")


def rename_and_move_files(source_dir, target_dir):
    """
    Renames and moves `.e57` files.
    """
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    try:
        files = sorted([f for f in os.listdir(source_dir) if f.endswith(".e57")])
        for index, file_name in enumerate(files):
            old_path = os.path.join(source_dir, file_name)
            new_name = f"treedis_{index}.e57"
            new_path = os.path.join(target_dir, new_name)

            logging.info(f"Renaming {old_path} to {new_path}...")
            os.rename(old_path, new_path)

        logging.info(f"All `.e57` files moved to {target_dir}.")
    except Exception as e:
        logging.error("Failed to rename and move files", exc_info=True)
        raise RuntimeError(f"Error renaming or moving files in {source_dir}: {e}") from e
    finally:
        shutil.rmtree(source_dir)
        logging.info(f"Source directory {source_dir} removed.")


def send_job_status_request(name, status, message):
    """
    Sends a job status update to the API.
    """
    api_domain = os.getenv("API_DOMAIN")
    endpoint = f"https://{api_domain}/v1/api/convert/updateJobStatus"
    payload = {"name": name, "status": status, "message": message}

    try:
        response = requests.post(endpoint, json=payload)
        if response.status_code == 200:
            logging.info(f"Job status updated successfully: {response.json()}")
        else:
            logging.error(f"API returned status {response.status_code}: {response.text}")

    except requests.exceptions.RequestException as e:
        logging.error(
            {
                "message": "Failed to send job status update",
                "error": str(e),
                "url": endpoint,
            },
            exc_info=True,
        )

def run_unpack_script():
    """
    Processes `.e57` files in the scans folder by unpacking and removing the originals.
    Raises errors if the folder doesn't exist or files cannot be processed.
    """
    scans_folder = "./scans"

    try:
        if not os.path.exists(scans_folder):
            logging.error(f"Folder not found: {scans_folder}")
            raise RuntimeError(f"The folder '{scans_folder}' does not exist.")

        if not os.access(scans_folder, os.R_OK | os.W_OK):
            logging.error(f"Permission denied for folder: {scans_folder}")
            raise PermissionError(f"Insufficient permissions for folder '{scans_folder}'.")

        for file_name in os.listdir(scans_folder):
            file_path = os.path.join(scans_folder, file_name)

            if os.path.isfile(file_path):
                try:
                    logging.info(f"Unpacking file: {file_name}")
                    unpack(file_path)
                    os.remove(file_path)
                    logging.info(f"Successfully processed and removed file: {file_name}")
                except Exception as e:
                    logging.error(f"Error unpacking file '{file_name}': {str(e)}", exc_info=True)
                    continue  # Skip the problematic file but continue processing other files

        logging.info("Unpack script completed successfully.")

    except Exception as e:
        logging.critical(f"An error occurred during unpacking: {str(e)}", exc_info=True)
        raise RuntimeError(f"Unpack script failed: {str(e)}") from e


def run_submit_script():
    """
    Submits processed folders in the scans directory.
    Deletes the scans folder upon successful completion.
    Raises errors for missing folders or processing issues.
    """
    scans_folder = f"/{ROOT_DIR}/scans"

    try:
        if not os.path.exists(scans_folder):
            logging.error(f"Folder not found: {scans_folder}")
            raise RuntimeError(f"The folder '{scans_folder}' does not exist.")

        if not os.access(scans_folder, os.R_OK | os.W_OK):
            logging.error(f"Permission denied for folder: {scans_folder}")
            raise PermissionError(f"Insufficient permissions for folder '{scans_folder}'.")

        processed_count = 0
        for item in os.listdir(scans_folder):
            folder_path = os.path.join(scans_folder, item)

            if os.path.isdir(folder_path) and item.endswith("-out"):
                try:
                    name = item.split("-out")[0]
                    logging.info(f"Submitting folder: {item} with name: {name}")
                    submit(name)
                    processed_count += 1
                except Exception as e:
                    logging.error(f"Error submitting folder '{item}': {str(e)}", exc_info=True)
                    continue  # Skip the problematic folder but continue processing others

        if processed_count == 0:
            logging.warning("No folders matching the criteria were found for submission.")

        # Remove the scans folder only if no exceptions occurred
        shutil.rmtree(scans_folder)
        logging.info(f"Submit script completed. Removed folder: {scans_folder}")

    except Exception as e:
        logging.critical(f"Submission failed: {str(e)}", exc_info=True)
        raise RuntimeError(f"Submit script failed: {str(e)}") from e



def upload_obj_to_s3():
    auth_key = os.getenv("MATTERPORT_OAUTH_TOKEN")
    matter_id = os.getenv("MATTERPORT_ID")
    tour_slug = os.getenv("TOUR_SLUG")
    output_file = "treedis_obj.zip"
    extract_to = "treedis_obj"
    s3_prefix = "ImmersalToursData"
    s3_bucket_name = os.getenv("S3_BUCKET_NAME")

    obj_url = fetch_matterport_assets(auth_key, matter_id, "mp:matterpak")
    download_file(obj_url, output_file)
    unzip_file(output_file, extract_to)

    # Initialize S3 client
    s3_client = boto3.client("s3")

    # Find the .obj file
    obj_file_path = None
    for root, dirs, files in os.walk(extract_to):
        for file in files:
            if file.endswith(".obj"):
                obj_file_path = Path(root) / file
                break
        if obj_file_path:
            break

    if obj_file_path:
        # Generate S3 key
        s3_key = f"{s3_prefix}/{tour_slug}/{tour_slug}.obj"
        print(f"Uploading to: {s3_key}")

        if not obj_file_path.exists():
            raise FileNotFoundError(f"The file {obj_file_path} does not exist.")

        # Upload the .obj file to S3
        try:
            s3_client.upload_file(
                Filename=str(obj_file_path),
                Bucket=s3_bucket_name,
                Key=s3_key,
                ExtraArgs={'ACL': 'public-read'}
            )
            print(f"Uploaded {obj_file_path} to s3://{s3_bucket_name}/{s3_key}")
        except Exception as e:
            raise Exception(f"Failed to upload {obj_file_path}: {e}")
    else:
        raise FileNotFoundError("No .obj file found in the extracted directory.")


def main():
    auth_key = os.getenv("MATTERPORT_OAUTH_TOKEN")
    matter_id = os.getenv("MATTERPORT_ID")

    if not auth_key or not matter_id:
        raise EnvironmentError(
            "Missing environment variables: MATTERPORT_OAUTH_TOKEN or MATTERPORT_ID."
        )

    output_file = f"/{ROOT_DIR}/treedis.zip"
    logging.info(output_file)
    extract_to = f"/{ROOT_DIR}/tmp_scans"
    logging.info(extract_to)
    scans_dir = f"/{ROOT_DIR}/scans"
    logging.info(scans_dir)
    try:
        asset_url = fetch_matterport_assets(auth_key, matter_id, "mp:e57")
        download_file(asset_url, output_file)
        unzip_file(output_file, extract_to)
        rename_and_move_files(extract_to, scans_dir)
        run_unpack_script()
        run_submit_script()
        upload_obj_to_s3()
    except Exception as e:
        logging.critical(f"Fatal error during execution: {str(e)}", exc_info=True)
        send_job_status_request(os.getenv("FILE_PREFIX"), "error", str(e))
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical("Program terminated with an error", exc_info=True)
        sys.exit(1)
