# Script para criar a Tarefa Agendada no Windows (Cron Job Nativo)
$taskName = "OPTCG_AutoUpdate"
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "$PSScriptRoot\update_all.py" -WorkingDirectory "$PSScriptRoot"
$trigger = New-ScheduledTaskTrigger -Daily -At 3:00AM

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Description "Atualização diária automática do OPTCG Database, Meta OP17 e Testes" -Force
Write-Host "Tarefa Agendada no Windows 'OPTCG_AutoUpdate' instalada com sucesso!"
