import os
import requests
from dotenv import load_dotenv
import zipfile
import shutil
from unpack import unpack
from submit import submit
import logging

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
        print(f"Error fetching assets: {e}")
        raise


def download_file(url, output_file):
    """
    Downloads a file from the given URL and saves it with the specified name.

    param url: The URL to download the file from.
    param output_file: The name of the file to save the downloaded content.
    return: None
    """
    try:
        print(f"Downloading from {url}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an error for HTTP status codes >= 400

        # Save the content to a file
        with open(output_file, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"File saved as {output_file}.")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading the file: {e}")
        raise


def unzip_file(zip_path, extract_to):
    """
    Unzips the specified zip file to a given directory and deletes the zip file afterward.

    param zip_path: Path to the zip file.
    param extract_to: Directory where the zip file will be extracted.
    return: None
    """
    try:
        print(f"Unzipping {zip_path} to {extract_to}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        print(f"Unzipped files to {extract_to}.")
    except zipfile.BadZipFile as e:
        print(f"Error unzipping file: {e}")
        raise
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            print(f"Deleted zip file: {zip_path}")


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

        print(f"Renaming {old_path} to {new_path}...")
        os.rename(old_path, new_path)

    # Remove the source directory after files are moved
    print(f"Removing source directory: {source_dir}...")
    shutil.rmtree(source_dir)
    print(f"All files have been renamed and moved to {target_dir}.")


def run_unpack_script():
    if __name__ == "__main__":
        # Directory containing the scans
        scans_folder = "./scans"

        try:
            # Check if the directory exists
            if not os.path.exists(scans_folder):
                print(f"The folder '{scans_folder}' does not exist.")
                return

            # Iterate over all files in the scans folder
            for file_name in os.listdir(scans_folder):
                # Create the full file path
                file_path = os.path.join(scans_folder, file_name)

                # Check if it's a file (not a directory)
                if os.path.isfile(file_path):
                    try:
                        # Run the unpack function
                        unpack(file_path)
                        os.remove(file_path)
                    except Exception as e:
                        print(f"Error unpacking file '{file_name}': {e}")
                        continue  # Skip to the next file

            print("Processing complete.")

        except Exception as e:
            print(f"An error occurred: {e}")


def run_submit_script():
    scans_folder = "./scans"

    # Check if the directory exists
    if not os.path.exists(scans_folder):
        print(f"The folder '{scans_folder}' does not exist.")
        return

    # Iterate through all items in the scans folder
    for item in os.listdir(scans_folder):
        # Create the full path
        folder_path = os.path.join(scans_folder, item)

        # Check if it's a directory and matches the naming convention
        if os.path.isdir(folder_path) and item.endswith("-out"):
            name = item.split("-out")[0]

            try:
                submit(name)
            except Exception as e:
                print(f"Error submitting {name}: {e}")

    shutil.rmtree(scans_folder)
    print("Processing submit complete.")


def main():
    # Load environment variables
    auth_key = os.getenv("MATTERPORT_OAUTH_TOKEN")
    matter_id = os.getenv("MATTERPORT_MATTER_ID")

    if not auth_key or not matter_id:
        print("Error: Missing required environment variables.")
        print("Ensure MATTERPORT_OAUTH_TOKEN and MATTERPORT_MATTER_ID are set.")
        return

    output_file = "treedis.zip"
    extract_to = "tmp_scans"
    scans_dir = "scans"

    try:
        # Fetch the asset URL
        asset_url = fetch_matterport_assets(auth_key, matter_id)

        # Download the file if the URL is available
        download_file(asset_url, output_file)

        # Unzip the downloaded file
        unzip_file(output_file, extract_to)

        # Rename and move `.e57` files to the scans folder
        rename_and_move_files(extract_to, scans_dir)

        run_unpack_script()

        run_submit_script()
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
