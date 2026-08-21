$ErrorActionPreference = 'Stop'
$cs = 'Provider=Microsoft.ACE.OLEDB.12.0;User ID=Admin;Data Source=D:\obsidian\demo\Excel面试实操题库.xlsx;Mode=Read;Extended Properties="Excel 12.0 Xml;HDR=YES;IMEX=1"'
$conn = New-Object -ComObject ADODB.Connection
$conn.Open($cs)

function Run-Query([string]$sql) {
    $rs = New-Object -ComObject ADODB.Recordset
    $rs.Open($sql, $conn, 0, 1)
    while (-not $rs.EOF) {
        $vals = @()
        foreach ($f in $rs.Fields) {
            $t = if ($null -eq $f.Value) { 'NULL' } else { $f.Value.GetType().Name }
            $vals += "[$($f.Name)]=$($f.Value) <$t>"
        }
        Write-Output ($vals -join ' ; ')
        $rs.MoveNext()
    }
    $rs.Close()
}

Write-Output '=== IMEX=1：各列 NULL 计数 ==='
Run-Query 'SELECT COUNT(*) AS cnt FROM [订单表_原始$A3:L211] WHERE [数量] IS NULL'
Run-Query 'SELECT COUNT(*) AS cnt FROM [订单表_原始$A3:L211] WHERE [金额(元)] IS NULL'
Run-Query 'SELECT COUNT(*) AS cnt FROM [订单表_原始$A3:L211] WHERE [下单日期] IS NULL'
Write-Output '=== IMEX=1：样例行（前5行）值与类型 ==='
Run-Query 'SELECT TOP 5 [下单日期],[数量],[金额(元)] FROM [订单表_原始$A3:L211]'
$conn.Close()

$cs2 = 'Provider=Microsoft.ACE.OLEDB.12.0;User ID=Admin;Data Source=D:\obsidian\demo\Excel面试实操题库.xlsx;Mode=Read;Extended Properties="Excel 12.0 Xml;HDR=YES"'
$conn2 = New-Object -ComObject ADODB.Connection
$conn2.Open($cs2)
function Run-Query2([string]$sql) {
    $rs = New-Object -ComObject ADODB.Recordset
    $rs.Open($sql, $conn2, 0, 1)
    while (-not $rs.EOF) {
        $vals = @()
        foreach ($f in $rs.Fields) {
            $t = if ($null -eq $f.Value) { 'NULL' } else { $f.Value.GetType().Name }
            $vals += "[$($f.Name)]=$($f.Value) <$t>"
        }
        Write-Output ($vals -join ' ; ')
        $rs.MoveNext()
    }
    $rs.Close()
}
Write-Output '=== 无IMEX(默认)：各列 NULL 计数 ==='
Run-Query2 'SELECT COUNT(*) AS cnt FROM [订单表_原始$A3:L211] WHERE [数量] IS NULL'
Run-Query2 'SELECT COUNT(*) AS cnt FROM [订单表_原始$A3:L211] WHERE [金额(元)] IS NULL'
Run-Query2 'SELECT COUNT(*) AS cnt FROM [订单表_原始$A3:L211] WHERE [下单日期] IS NULL'
$conn2.Close()
