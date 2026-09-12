$slicer = "C:\Users\paul.joy\AppData\Local\slicer.org\Slicer-5.12.3\Slicer.exe"
$modulePath = "C:\Users\paul.joy\Projects\VATQuant\VATQuant"
Start-Process $slicer -ArgumentList @("--additional-module-path", $modulePath)
