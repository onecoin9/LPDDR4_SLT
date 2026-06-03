using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.IO;
using System.Timers;
using System.Threading;

namespace Hsg.Common
{
    public delegate void TimeoutEventHandler(int TimerId);
    public class TimerTask
    {
        struct MyTimer
        {
            public bool valid;// 是否为有效的TIMER
            public TimeoutEventHandler evenHdr;
            public bool repeatFlag;// once or circle.
            public int intervalMsec;// inverval msecond
            public DateTime startTime;
            public int timerId;
       
            public bool CheckTimeIsOver()
            {
                // DateTime overTimer = startTime;
                DateTime overTimer = startTime.AddMilliseconds(intervalMsec);
                if (overTimer <= DateTime.Now)
                {
                    return true;
                }
                return false;
            }
            public DateTime GetOverTime()
            {
                // DateTime overTimer = startTime;
                DateTime overTimer = startTime.AddMilliseconds(intervalMsec);
                return overTimer;
            }
        }
        private static TimerTask _instance = new TimerTask();
        private System.Timers.Timer _timer;
        public static int INVALID_TIMER_ID = -1;
        private const int MAX_TIMER_COUNT = 1024;
        private SortedList<int, MyTimer> _timerList;
        private int _lastRequestId = 0;
        private static readonly Object _mutexLock = new object();
        // 全局定义信号量（例如最大并发数 10）
        private static SemaphoreSlim _semaphore = new SemaphoreSlim(20);
        private TimerTask()
        {
            //_timerList = new MyTimer[MAX_TIMER_COUNT];
            _timerList = new SortedList<int, MyTimer>();
            _timer = new System.Timers.Timer();
            _timer.Elapsed += new ElapsedEventHandler(TimerEventHandle);
            _timer.Interval = 1000;
            _timer.Enabled = true;
            _timer.AutoReset = false;
        }
        public static TimerTask GetTimerTaskInstance()
        {
            return _instance;
        }

        private void TimerEventHandle(object sender, ElapsedEventArgs args)
        {
            DateTime minTimer = DateTime.Now.AddHours(1);
            //   int nextTaskId = -1;
            List<TimeoutEventHandler> eventList = new List<TimeoutEventHandler>();
            List<int> timerIds = new List<int>();
            lock (_mutexLock)
            {
                //Hlog.D("lock B");
                //Hlog.D(String.Format(@"timeout start{0}", _timerList.Count()));

                for (int i = _timerList.Count() - 1; i >= 0; i--)
                {
                    if (_timerList.Values[i].valid)
                    {
                        if (_timerList.Values[i].CheckTimeIsOver())
                        {
                            //Hlog.I($"CheckTimeIsOver {i} {_timerList[i].startTime} {_timerList[i].intervalMsec} ");
                            int id = _timerList.Values[i].timerId;
                            MyTimer temp = _timerList.Values[i];
                            eventList.Add(_timerList[id].evenHdr);
                            timerIds.Add(id);

                            if (!temp.repeatFlag)
                            {
                                temp.valid = false;
                            }
                            else
                            {
                                temp.startTime = DateTime.Now;
                            }
                            _timerList[id] = temp;
                        }
                    }
                    if (_timerList.Values[i].valid)
                    {
                        DateTime overTime = _timerList.Values[i].GetOverTime();
                        //Hlog.I(string.Format(@"check time{0} interval:{1}", i, _timerList[i].intervalMsec));
                        if (minTimer.CompareTo(overTime) >= 0)
                        {
                            minTimer = overTime;
                            //nextTaskId = i;
                            //Hlog.D(string.Format(@"next time{0}", i));
                        }
                    }
                    else
                    {
                        _timerList.RemoveAt(i);
                    }
                }
                TimeSpan tSpan = new TimeSpan(minTimer.Ticks - DateTime.Now.Ticks);
                _timer.Interval = Math.Max(1, (int)tSpan.TotalMilliseconds);
                _timer.Start();
                //Hlog.D(string.Format(@"start timer:{0}", _timer.Interval));
            }
            //if (eventList.Count > 0)
            //{
            //    Task.Run(() =>
            //    {
            //        for (int i = 0; i < eventList.Count; i++)
            //        {
            //            eventList[i]?.Invoke(timerIds[i]);
            //        }
            //    });
            //}
            if (eventList.Count > 0)
            {
                for (int i = 0; i < eventList.Count; i++)
                {
                    TimeoutEventHandler handler = eventList[i];
                    int timerId = timerIds[i];
                    Task.Run(async () =>
                    {
                        await _semaphore.WaitAsync();
                        try
                        {
                            handler?.Invoke(timerId);
                        }
                        catch (Exception ex)
                        {
                            Hlog.E("EventError", $"Timer {timerId} 事件异常: {ex.Message}");
                        }
                        finally
                        {
                            _semaphore.Release();
                        }
                    });
                }
            }
        }
        public int StartTimer(int intervalMsec, bool repeatFlag, TimeoutEventHandler evenHandler)
        {
            MyTimer temp = new MyTimer();
            lock (_mutexLock)
            {
                if (_timerList.Count >= MAX_TIMER_COUNT)
                {
                    Hlog.D(String.Format(@"timeout BEYOND MAX {0}", _timerList.Count()));
                    return TimerTask.INVALID_TIMER_ID;
                }
                do
                {
                    _lastRequestId++;
                } while (_timerList.TryGetValue(_lastRequestId, out temp) || _lastRequestId == INVALID_TIMER_ID);

                if (_timer.Interval > intervalMsec)// 如果时间不对，里面停止重新计算
                {
                    _timer.Stop();
                    _timer.Interval = 1;
                }

                temp.repeatFlag = repeatFlag;
                temp.evenHdr = evenHandler;
                temp.intervalMsec = intervalMsec;
                temp.valid = true;
                temp.startTime = DateTime.Now;
                temp.timerId = _lastRequestId;
                _timerList.Add(_lastRequestId, temp);
                //_timerList[i] = tmpTime;
                if (!_timer.Enabled)
                {
                    _timer.Start();
                }
                Hlog.D("Timer", string.Format(@"start timer {0}:{1} {2}", _timerList.Count, _lastRequestId, intervalMsec));
                return _lastRequestId;
            }
        }
        public void StopTimer(ref int timerId)
        {
            Hlog.D("Timer", string.Format(@"StopTimer {0}", timerId));
            if (timerId == INVALID_TIMER_ID)
            {
                return;
            }
            lock (_mutexLock)
            {
                MyTimer temp;
                if (_timerList.TryGetValue(timerId, out temp))
                {
                    _timerList.Remove(timerId);
                }
                timerId = INVALID_TIMER_ID;
            }
        }
    }
}
