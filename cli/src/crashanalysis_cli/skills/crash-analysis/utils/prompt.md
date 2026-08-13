好的，先不做修改，给出这一步要修改的文件和在整个流程中的影响范围

crash ps  收集所有 UN（D 状态）PID
crash bt -a  从全 CPU/线程栈里找 RIP
crash bt <D状态任务PID>
crash foreach UN bt 