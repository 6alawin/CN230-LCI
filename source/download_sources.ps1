$ErrorActionPreference = 'Stop'

$datasets = @(
    @{ src_code = 'SRC-01'; dataset_id = 'dataset_11_07'; dataset_name = 'การผลิตน้ำมันดิบ' },
    @{ src_code = 'SRC-02'; dataset_id = 'dataset_11_08'; dataset_name = 'การผลิตคอนเดนเสท' },
    @{ src_code = 'SRC-03'; dataset_id = 'dataset_11_09'; dataset_name = 'การนำเข้าน้ำมันดิบ' },
    @{ src_code = 'SRC-04'; dataset_id = 'dataset_11_13'; dataset_name = 'การใช้น้ำมันในการกลั่น' },
    @{ src_code = 'SRC-05'; dataset_id = 'dataset_11_14'; dataset_name = 'การผลิตน้ำมันสำเร็จรูป' },
    @{ src_code = 'SRC-06'; dataset_id = 'dataset_11_16'; dataset_name = 'การนำเข้าน้ำมันสำเร็จรูป' },
    @{ src_code = 'SRC-07'; dataset_id = 'dataset_11_17'; dataset_name = 'การส่งออกน้ำมันสำเร็จรูป' },
    @{ src_code = 'SRC-08'; dataset_id = 'dataset_11_15'; dataset_name = 'การใช้น้ำมันสำเร็จรูป' },
    @{ src_code = 'SRC-09'; dataset_id = 'dataset_11_19'; dataset_name = 'LPG โพรเพน และบิวเทน' },
    @{ src_code = 'SRC-10'; dataset_id = 'dataset_11_20'; dataset_name = 'การผลิตและนำเข้าก๊าซธรรมชาติ' },
    @{ src_code = 'SRC-11'; dataset_id = 'dataset_11_22'; dataset_name = 'การใช้ก๊าซธรรมชาติรายสาขา' },
    @{ src_code = 'SRC-12'; dataset_id = 'dataset_11_21'; dataset_name = 'การกระจาย NGL' },
    @{ src_code = 'SRC-13'; dataset_id = 'dataset_11_23'; dataset_name = 'การผลิตและใช้ลิกไนต์' },
    @{ src_code = 'SRC-14'; dataset_id = 'dataset_11_25'; dataset_name = 'การนำเข้าถ่านหิน' },
    @{ src_code = 'SRC-15'; dataset_id = 'dataset_11_24'; dataset_name = 'การใช้ลิกไนต์และถ่านหิน' },
    @{ src_code = 'SRC-16'; dataset_id = 'dataset_11_68'; dataset_name = 'การผลิต B100' },
    @{ src_code = 'SRC-17'; dataset_id = '2da06207-1cde-4064-b849-6cdea6f99422'; dataset_name = 'การผลิตเอทานอล' },
    @{ src_code = 'SRC-18'; dataset_id = 'dataset_11_65'; dataset_name = 'การปล่อย CO2 ในสาขาเศรษฐกิจอื่นๆ' },
    @{ src_code = 'SRC-19'; dataset_id = 'dataset_11_64'; dataset_name = 'การปล่อย CO2 ในภาคอุตสาหกรรม' },
    @{ src_code = 'SRC-20'; dataset_id = 'dataset_11_63'; dataset_name = 'การปล่อย CO2 ในภาคขนส่ง' },
    @{ src_code = 'SRC-21'; dataset_id = 'dataset_11_62'; dataset_name = 'การปล่อย CO2 ในการผลิตไฟฟ้า' }
)

$accessedDate = Get-Date -Format 'yyyy-MM-dd'
$publisher = 'ศูนย์เทคโนโลยีสารสนเทศและการสื่อสาร (ศท.)'
$owner = 'สำนักงานนโยบายและแผนพลังงาน (EPPO)'
$metadata = foreach ($dataset in $datasets) {
    $apiUrl = 'https://catalog.eppo.go.th/api/3/action/package_show?id=' + $dataset.dataset_id
    Start-Sleep -Seconds 2
    $package = $null
    for ($attempt = 1; $attempt -le 6; $attempt++) {
        try {
            $package = Invoke-RestMethod -Uri $apiUrl -Headers @{ 'User-Agent' = 'CN230-PortugalSQL-source-downloader/1.0' }
            break
        } catch {
            if ($_.Exception.Message -notmatch '429|Too Many Requests' -or $attempt -eq 6) { throw }
            $delay = [Math]::Min(60, 10 * $attempt)
            Write-Host "Rate limited while reading $($dataset.src_code); retrying in $delay seconds"
            Start-Sleep -Seconds $delay
        }
    }
    if (-not $package.success) {
        throw "EPPO API did not return a dataset for $($dataset.src_code)"
    }

    $csvResources = @($package.result.resources | Where-Object { $_.format -match '^CSV$' })
    if ($csvResources.Count -ne 1) {
        throw "$($dataset.src_code) should have exactly one CSV resource; found $($csvResources.Count)"
    }

    $downloadUrl = [string]$csvResources[0].url
    if (-not $downloadUrl.StartsWith('https://catalog.eppo.go.th/')) {
        throw "Unexpected download host for $($dataset.src_code): $downloadUrl"
    }

    $csvPath = Join-Path $PSScriptRoot ($dataset.src_code + '.csv')
    if (-not (Test-Path -LiteralPath $csvPath) -or (Get-Item -LiteralPath $csvPath).Length -eq 0) {
        for ($attempt = 1; $attempt -le 6; $attempt++) {
            try {
                Invoke-WebRequest -Uri $downloadUrl -OutFile $csvPath -Headers @{ 'User-Agent' = 'CN230-PortugalSQL-source-downloader/1.0' }
                break
            } catch {
                if ($_.Exception.Message -notmatch '429|Too Many Requests' -or $attempt -eq 6) { throw }
                $delay = [Math]::Min(60, 10 * $attempt)
                Write-Host "Rate limited while downloading $($dataset.src_code); retrying in $delay seconds"
                Start-Sleep -Seconds $delay
            }
        }
    }
    if ((Get-Item -LiteralPath $csvPath).Length -eq 0) {
        throw "Downloaded CSV is empty: $($dataset.src_code)"
    }

    [pscustomobject]@{
        src_code      = $dataset.src_code
        dataset_name  = $dataset.dataset_name
        agency        = $publisher
        data_owner    = $owner
        url           = 'https://catalog.eppo.go.th/dataset/' + $dataset.dataset_id
        accessed_date = $accessedDate
        csv_file      = $dataset.src_code + '.csv'
    }
    Write-Host "Downloaded $($dataset.src_code) -> $csvPath"
}

$metadata | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'source_metadata.csv') -NoTypeInformation -Encoding utf8
Write-Host "Saved metadata for $($datasets.Count) sources to source_metadata.csv"
