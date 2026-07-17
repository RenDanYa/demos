$dir = 'd:\obsidian\demo\05_long_project\小红书'
$outFile = 'd:\obsidian\demo\05_long_project\小红书\待办\婚礼筹备.md'

$files = Get-ChildItem -Path $dir -Filter '*.md' -Recurse -File | Where-Object {
    $_.Name -ne '_运行日志.md' -and $_.FullName -notlike '*\待办\*'
}

$notes = @()
$totalTasks = 0

foreach ($file in $files) {
    $content = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8)
    if (-not ($content -match '##\s*待办')) { continue }

    # 解析 frontmatter 中的 todo_generated
    $todoGenerated = ''
    if ($content -match '^---\s*\r?\n') {
        $parts = $content -split '\r?\n---\r?\n', 3
        if ($parts.Count -ge 2) {
            $fm = $parts[1]
            if ($fm -match 'todo_generated:\s*(.+?)\r?$') {
                $todoGenerated = $matches[1].Trim()
            }
        }
    }

    if ($todoGenerated -eq '无') { continue }

    # 统计 - [ ] 任务数
    $taskMatches = [regex]::Matches($content, '(?m)^\s*-\s*\[\s\]\s*.*$')
    $taskCount = $taskMatches.Count
    $totalTasks += $taskCount

    # 提取分组名称
    $groups = @()
    $idx = $content.IndexOf('## 待办')
    if ($idx -ge 0) {
        $block = $content.Substring($idx)
        $lines = $block -split '\r?\n'
        for ($i = 1; $i -lt $lines.Count; $i++) {
            $line = $lines[$i]
            if ($line -match '^##\s') { break }
            if ($line -match '^###\s+(.+)$') {
                $groups += $matches[1].Trim()
            }
        }
    }

    $notes += [PSCustomObject]@{
        Name      = $file.Name
        BaseName  = $file.BaseName
        Timestamp = $todoGenerated
        Groups    = $groups
        Tasks     = $taskCount
    }
}

$notes = $notes | Sort-Object BaseName

Write-Host "符合条件的笔记数量: $($notes.Count)"
Write-Host "总任务数: $totalTasks"

if ($notes.Count -ne 44) {
    Write-Warning "笔记数量不是 44，请检查源文件。"
}

$now = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$groupText = ($notes.Groups | ForEach-Object { $_ }) -join '、'  # not used directly

# 构建 markdown
$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine('---')
[void]$sb.AppendLine('tags: [待办]')
[void]$sb.AppendLine('theme: 婚礼筹备')
[void]$sb.AppendLine("updated: $now")
[void]$sb.AppendLine('---')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('# 婚礼筹备待办汇总')
[void]$sb.AppendLine('')
[void]$sb.AppendLine("> 来源目录：d:\obsidian\demo\05_long_project\小红书")
[void]$sb.AppendLine("> 最后更新：$now")
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## 进度概览')
[void]$sb.AppendLine('')
[void]$sb.AppendLine("> 总任务：$totalTasks ｜ 已完成：0 ｜ 完成率：0%")
[void]$sb.AppendLine("> 已收录笔记：$($notes.Count) 篇")
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## 已收录笔记')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('> 本清单是「笔记级双链登记表」，记录所有已向本汇总文件贡献任务的笔记。')
[void]$sb.AppendLine('')

$idx = 1
foreach ($n in $notes) {
    $g = ($n.Groups -join '、')
    if ([string]::IsNullOrEmpty($g)) { $g = '无' }
    [void]$sb.AppendLine("$idx. [[$($n.Name)]] — $($n.Timestamp) — 分组：$g")
    $idx++
}

[void]$sb.AppendLine('')
[void]$sb.AppendLine('---')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## 🔗 分组索引')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('> 使用嵌入块直接引用源文件的整个 `## 待办` 区块，避免重复管理任务实体')
[void]$sb.AppendLine('')

foreach ($n in $notes) {
    [void]$sb.AppendLine("### $($n.Name)")
    [void]$sb.AppendLine('')
    [void]$sb.AppendLine("- ![[$($n.Name)#待办]]")
    [void]$sb.AppendLine('')
}

$content = $sb.ToString()

# 确保目标目录存在
$outDir = Split-Path -Parent $outFile
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }

# 使用无 BOM 的 UTF-8 写入
$encoding = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($outFile, $content, $encoding)

Write-Host "已写入: $outFile"
