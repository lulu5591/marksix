param(
  [string]$RepoName = "lottery"
)

Write-Host "== GitHub Setup =="

$sshDir = Join-Path $env:USERPROFILE ".ssh"
if (!(Test-Path $sshDir)) { New-Item -ItemType Directory -Path $sshDir | Out-Null }

$keyPath = Join-Path $sshDir "id_ed25519"
if (!(Test-Path $keyPath)) {
  Write-Host "Generating SSH key (ed25519) ..."
  ssh-keygen -t ed25519 -C "lottery-app" -f $keyPath
} else {
  Write-Host "SSH key already exists: $keyPath"
}

$pub = Get-Content ("$keyPath.pub") -Raw
Write-Host "\nPublic key (add to GitHub → Settings → SSH and GPG keys):"
Write-Host "----------------------------------------"
Write-Host $pub
Write-Host "----------------------------------------"

$username = Read-Host "Enter your GitHub username"
if (!$username) { Write-Error "Username required"; exit 1 }

$remote = "git@github.com:$username/$RepoName.git"
Write-Host "Setting remote origin to $remote"
git remote remove origin 2>$null
git remote add origin $remote

Write-Host "Pushing to GitHub (main) ..."
git push -u origin main

Write-Host "Done"

