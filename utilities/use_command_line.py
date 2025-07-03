import logging
import shlex
import subprocess

def run_cmd(cmd):
    if isinstance(cmd, list):
        printable = ' '.join(shlex.quote(str(c)) for c in cmd)
    else:
        printable = cmd
    logging.info(f"\n>>> Running: {printable}\n")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logging.info("Command failed with error:")
        logging.info(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd)
    if result.stdout:
        logging.info(result.stdout)
