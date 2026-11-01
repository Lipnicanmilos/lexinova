# Vyrobi logo, ikony, favicon a OG obrazok zo zdrojov v scripts/brand.
# Node ani Pillow na stroji nie su: SVG vykresli Edge bez okna, zmensi .NET.
#   powershell -ExecutionPolicy Bypass -File scripts\make_brand_images.ps1

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$root   = Split-Path $PSScriptRoot -Parent
$brand  = Join-Path $PSScriptRoot 'brand'
$static = Join-Path $root 'app\static'
$edge   = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
$work   = Join-Path $env:TEMP 'lexinova-brand'
New-Item -ItemType Directory -Force $work | Out-Null

function Render($source, $target, $width, $height, $transparent) {
    $url = 'file:///' + ($source -replace '\\', '/')
    $edgeArgs = @(
        '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
        '--allow-file-access-from-files', '--force-device-scale-factor=1',
        "--user-data-dir=$work\profile", '--virtual-time-budget=4000',
        "--window-size=$width,$height", "--screenshot=$target", $url
    )
    if ($transparent) { $edgeArgs += '--default-background-color=00000000' }
    $process = Start-Process $edge -ArgumentList $edgeArgs -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0 -or -not (Test-Path $target)) { throw "Render zlyhal: $source" }
}

function Scale($source, $size, $radius) {
    $bitmap = New-Object System.Drawing.Bitmap $size, $size, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.InterpolationMode = 'HighQualityBicubic'
    $graphics.PixelOffsetMode = 'HighQuality'
    $graphics.SmoothingMode = 'HighQuality'
    $attributes = New-Object System.Drawing.Imaging.ImageAttributes
    $attributes.SetWrapMode('TileFlipXY')
    $image = [System.Drawing.Image]::FromFile($source)
    $rect = New-Object System.Drawing.Rectangle 0, 0, $size, $size
    $graphics.DrawImage($image, $rect, 0, 0, $image.Width, $image.Height, 'Pixel', $attributes)
    $image.Dispose(); $graphics.Dispose()
    if ($radius -eq 0) { return $bitmap }

    # Zaoblene rohy pre karty v prehliadaci, ostatne ikony oreze system sam.
    $rounded = New-Object System.Drawing.Bitmap $size, $size, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [System.Drawing.Graphics]::FromImage($rounded)
    $graphics.SmoothingMode = 'AntiAlias'
    $d = 2 * $radius
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $path.AddArc(0, 0, $d, $d, 180, 90)
    $path.AddArc($size - $d - 1, 0, $d, $d, 270, 90)
    $path.AddArc($size - $d - 1, $size - $d - 1, $d, $d, 0, 90)
    $path.AddArc(0, $size - $d - 1, $d, $d, 90, 90)
    $path.CloseFigure()
    $brush = New-Object System.Drawing.TextureBrush $bitmap
    $graphics.FillPath($brush, $path)
    $brush.Dispose(); $path.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
    return $rounded
}

function SavePng($bitmap, $target) {
    $bitmap.Save($target, [System.Drawing.Imaging.ImageFormat]::Png)
    $bitmap.Dispose()
}

function SaveIco($master, $sizes, $radiusRatio, $target) {
    # ICO s PNG vnutri: hlavicka, zoznam velkosti a potom samotne obrazky.
    $images = foreach ($size in $sizes) {
        $bitmap = Scale $master $size ([int]($size * $radiusRatio))
        $stream = New-Object System.IO.MemoryStream
        $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
        $bitmap.Dispose()
        , $stream.ToArray()
    }
    $file = [System.IO.File]::Create($target)
    $writer = New-Object System.IO.BinaryWriter $file
    $writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$sizes.Count)
    $offset = 6 + 16 * $sizes.Count
    for ($i = 0; $i -lt $sizes.Count; $i++) {
        $writer.Write([byte]$sizes[$i]); $writer.Write([byte]$sizes[$i])
        $writer.Write([byte]0); $writer.Write([byte]0)
        $writer.Write([uint16]1); $writer.Write([uint16]32)
        $writer.Write([uint32]$images[$i].Length); $writer.Write([uint32]$offset)
        $offset += $images[$i].Length
    }
    foreach ($bytes in $images) { $writer.Write([byte[]]$bytes) }
    $writer.Dispose(); $file.Dispose()
}

$big   = Join-Path $work 'logo.png'
$small = Join-Path $work 'logo-small.png'
$og    = Join-Path $work 'og.png'
Render (Join-Path $brand 'logo.svg') $big 1024 1024 $false
Render (Join-Path $brand 'logo-small.svg') $small 1024 1024 $false
Render (Join-Path $brand 'og.html') $og 1200 630 $false

SavePng (Scale $big 512 0) (Join-Path $static 'icons\icon-512x512.png')
SavePng (Scale $big 192 0) (Join-Path $static 'icons\icon-192x192.png')
SavePng (Scale $big 180 0) (Join-Path $static 'apple-touch-icon.png')
SavePng (Scale $small 96 0) (Join-Path $static 'logo.png')
SaveIco $small @(16, 32, 48) 0.2 (Join-Path $static 'favicon.ico')

$jpeg = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
$quality = New-Object System.Drawing.Imaging.EncoderParameters 1
$quality.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality), 90L
$image = [System.Drawing.Image]::FromFile($og)
$image.Save((Join-Path $static 'img\og-image.jpg'), $jpeg, $quality)
$image.Dispose()

Write-Output 'Hotovo.'
