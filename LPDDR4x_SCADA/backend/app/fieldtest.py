"""Production entry point for the configured single-board UDP transport."""
from fastapi import HTTPException

from .manualrun import ACTIVE
from .sequencer import SequencerBusyError


class FieldTests:
    def __init__(self, cfg, runner, sequencer):
        self.cfg, self.runner, self.seq = cfg, runner, sequencer

    @property
    def enabled(self):
        return self.runner.mdbg.enabled and self.cfg.get('sites', {}).get('mode') == 'legacy'

    def mapping(self):
        return {(1, self.runner._ch(d)): d for d in self.runner._duts}

    def available(self, site=1):
        return [slot for (sid, slot), d in self.mapping().items()
                if sid == site and d in self.runner._transports
                and self.runner._st[d]['state'] not in ACTIVE
                and not self.runner._st[d].get('powerAction')
                and id(self.runner._st[d]) not in self.runner._drain_tasks]

    async def start(self, targets, batch, cfg_text, plan, *, origin='monitor', io_control=None):
        if self.seq.reserved:
            raise SequencerBusyError('扫描作业进行中，不能开始测试')
        if self.runner.power_lock.locked():
            raise HTTPException(409, '电源操作进行中，请稍后重试 / Power operation in progress')
        mapping = self.mapping()
        targets = list(dict.fromkeys(targets))
        if any(key not in mapping for key in targets):
            raise HTTPException(400, '请求包含未配置的现场通道 / Unconfigured field channel')
        selected = [key for key in targets if key[1] in self.available(key[0])]
        if not selected:
            raise HTTPException(409, '没有空闲且接收端口可用的通道 / No idle channel with a working receive port')
        if io_control is not None and io_control.action != 'none':
            lines = getattr(self.runner.mdbg, 'dut_key_lines', [])
            if any(mapping[key] > len(lines) for key in selected):
                raise HTTPException(409, '未配置所选通道的开机按键线 / Configure boot key lines first')
        # Admission and reservation are synchronous; hardware work starts on the next loop turn.
        self.runner.start_production([mapping[key] for key in selected], cfg_text,
                                     batch, plan, origin=origin, io_control=io_control,
                                     ready_limit=self.seq.boot_timeout_sec,
                                     run_limit=self.seq.test_timeout)
        return selected

    async def stop(self, targets=None):
        wanted = None if targets is None else set(targets)
        contexts = [(d, ctx) for d, ctx in self.runner._st.items()
                    if ctx.get('origin') in ('monitor', 'handler')
                    and (ctx['state'] in ACTIVE or ctx.get('powerAction'))
                    and (wanted is None or (1, ctx['channel']) in wanted)]
        # Mark cancellation before waiting for any already-issued Modbus operation.
        for d, ctx in contexts:
            ctx['_stopRequested'] = True
            self.runner.disarm(d)
        async with self.runner.power_lock:
            for d, ctx in contexts:
                if self.runner._resolve(ctx) is None:
                    continue
                ctx.update(powerAction='turning_off', power_pending=True)
                self.runner._notify_change()
                try:
                    await self.runner._io(self.runner.mdbg.set_power, d, False)
                except Exception as exc:
                    ctx['powerError'] = str(exc)
                    self.runner.hub.syslog('ERROR', f"CH{ctx['channel']:02d} 停止后下电失败: {exc}")
                    self.runner._set(d, 'fail', f'停止后下电失败: {exc}')
                finally:
                    ctx.update(powerAction='', power_pending=False)
                    self.runner._notify_change()
        return [(1, ctx['channel']) for _, ctx in contexts]
