# cd /usr/local/bin
# create .env

# vi .env
DB_NAME=mu_app
DB_USER=root (User-name)
DB_PASSWORD=123456
DB_HOST=localhost
S3_BUCKET=S2-BUCKET-NAME
S3_PREFIX=
LOCAL_BACKUP_DIR=/var/backups/mariadb
MAX_BACKUPS=15

# vi database-backup.py 
import boto3
import subprocess
import os
import datetime

# Load .env manually 
def load_env_file(env_path):
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

# Load .env (same directory as script)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_env_file(os.path.join(BASE_DIR, ".env"))

# ==== CONFIG from .env ====
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")

S3_BUCKET = os.getenv("S3_BUCKET")
S3_PREFIX = os.getenv("S3_PREFIX", "").strip("/")  # allow empty
LOCAL_BACKUP_DIR = os.getenv("LOCAL_BACKUP_DIR", "/var/backups/mariadb")
MAX_BACKUPS = int(os.getenv("MAX_BACKUPS", 15))


def run_backup():
    os.makedirs(LOCAL_BACKUP_DIR, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = f"{LOCAL_BACKUP_DIR}/{DB_NAME}_{timestamp}.sql.gz"

    print(f"[INFO] Dumping {DB_NAME} to {backup_file}")

    # mysqldump command using env variables
    dump_cmd = [
        "mysqldump",
        f"-u{DB_USER}",
        f"-p{DB_PASSWORD}",
        f"-h{DB_HOST}",
        "--single-transaction", "--quick", "--routines", "--triggers",
        "--events", "--hex-blob",
        "--databases", DB_NAME
    ]

    with open(backup_file, "wb") as f:
        proc = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE)
        gzip_proc = subprocess.Popen(["gzip"], stdin=proc.stdout, stdout=f)
        proc.stdout.close()
        gzip_proc.communicate()

    print("[INFO] Uploading to S3")
    s3 = boto3.client("s3")

    if S3_PREFIX:
        key = f"{S3_PREFIX}/{os.path.basename(backup_file)}"
    else:
        key = os.path.basename(backup_file)

    s3.upload_file(backup_file, S3_BUCKET, key)

    print("[INFO] Uploaded as:", f"s3://{S3_BUCKET}/{key}")

    enforce_retention_s3(s3)
    enforce_retention_local()


def enforce_retention_s3(s3):
    """Keep only the latest MAX_BACKUPS in S3."""
    print(f"[INFO] Enforcing S3 retention: keeping last {MAX_BACKUPS} backups")

    prefix = S3_PREFIX if S3_PREFIX else ""
    response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)

    if "Contents" not in response:
        return

    backups = sorted(response["Contents"], key=lambda x: x["LastModified"], reverse=True)

    if len(backups) > MAX_BACKUPS:
        old = backups[MAX_BACKUPS:]
        for obj in old:
            print(f"[INFO] Deleting old S3 backup: {obj['Key']}")
            s3.delete_object(Bucket=S3_BUCKET, Key=obj["Key"])


def enforce_retention_local():
    """Keep only the latest MAX_BACKUPS locally."""
    print(f"[INFO] Enforcing local retention: keeping last {MAX_BACKUPS} backups")

    files = sorted(
        [f for f in os.listdir(LOCAL_BACKUP_DIR) if f.endswith(".sql.gz")],
        key=lambda x: os.path.getmtime(os.path.join(LOCAL_BACKUP_DIR, x)),
        reverse=True,
    )

    if len(files) > MAX_BACKUPS:
        old = files[MAX_BACKUPS:]
        for f in old:
            path = os.path.join(LOCAL_BACKUP_DIR, f)
            print(f"[INFO] Deleting old local backup: {path}")
            os.remove(path)


if __name__ == "__main__":
    run_backup()
