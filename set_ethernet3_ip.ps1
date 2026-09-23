$logPath = "d:\Studies\SIH 2026\set_ip.log"
try {
    $adapter = Get-NetAdapter -Name "Ethernet 3" -ErrorAction Stop
    $idx = $adapter.ifIndex
    "Configuring adapter Ethernet 3 (ifIndex $idx)..." | Out-File -FilePath $logPath -Encoding utf8
    
    # Remove existing IPv4 addresses
    Get-NetIPAddress -InterfaceIndex $idx -AddressFamily IPv4 -ErrorAction SilentlyContinue | ForEach-Object {
        "Removing old IP $($_.IPAddress)..." | Out-File -FilePath $logPath -Append -Encoding utf8
        Remove-NetIPAddress -InterfaceIndex $idx -IPAddress $_.IPAddress -Confirm:$false -ErrorAction SilentlyContinue
    }
    
    # Assign 192.168.50.1/24
    "Assigning 192.168.50.1/24..." | Out-File -FilePath $logPath -Append -Encoding utf8
    $res = New-NetIPAddress -InterfaceIndex $idx -IPAddress 192.168.50.1 -PrefixLength 24 -ErrorAction Stop
    "Successfully assigned 192.168.50.1/24" | Out-File -FilePath $logPath -Append -Encoding utf8
    
    # Reset DNS
    Set-DnsClientServerAddress -InterfaceIndex $idx -ResetServerAddresses -ErrorAction SilentlyContinue
    "DNS reset." | Out-File -FilePath $logPath -Append -Encoding utf8
} catch {
    "ERROR: $_" | Out-File -FilePath $logPath -Append -Encoding utf8
}
