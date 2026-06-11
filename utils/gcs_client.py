from google.cloud import storage


def load_mapping(bucket_name):
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    paths = [
        "reference/mapping_and_control_design_reference.txt",
        "prompts/mapping_and_control_design_reference.txt",
        "mapping_and_control_design_reference.txt",
    ]

    for path in paths:
        blob = bucket.blob(path)
        if blob.exists():
            return blob.download_as_text()

    return "Mapping reference not found in GCS."
