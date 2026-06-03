using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using PooledAwait;
namespace Hsg.Common
{
    /// <summary>
    /// 
    /// </summary>
    /// <typeparam name="T1">状态</typeparam>
    /// <typeparam name="T2">事件</typeparam>
    public abstract class StateMechine<T1, T2>
    {
        private const int SUSPEND_NONE = 0;
        private const int SUSPEND_DONE = 1;
        private int _suspendStatet = SUSPEND_DONE;
        //public bool SusPend
        //{
        //    get { return Interlocked.CompareExchange(ref _suspendStatet, SUSPEND_DONE, SUSPEND_DONE) == SUSPEND_DONE; }
        //}
        private bool SusPend
        {
            get
            {
                if (_suspendStatet == SUSPEND_DONE)
                {
                    return true;
                }
                return false;
            }
        }
        private readonly ConcurrentDictionary<int, ValueTaskCompletionSource<bool>> _replyExpectedMsgs = new ConcurrentDictionary<int, ValueTaskCompletionSource<bool>>();
        private T1 _curState;
        private T2 _nextEvent;
        //private T1 _resumeState;
        protected string _stateName;
        protected string Mod { get; }
        //bool _bCreateThread;// 是否需要单独的线程
        //private AutoResetEvent _semEvent;
        public T1 CurState { get { return _curState; } }
        private readonly object _statelock = new object();
        private readonly object _eventlock = new object();
        private ConcurrentQueue<Tuple<T2, Object>> _eventQueue = new ConcurrentQueue<Tuple<T2, object>>();
        private Dictionary<Tuple<T1, T2>, Func<Object, T1>> _stateActions = new Dictionary<Tuple<T1, T2>, Func<object, T1>>();
        private Dictionary<T2, Func<Object, T1>> _globalActions = new Dictionary<T2, Func<object, T1>>();
        //  public Dictionary<Tuple<T1, T2>, Func<Object, T1>> StateActions;
        private TimerTask _timerTask;
        private SortedList<int, Tuple<bool, T2>> _timerEventList;
        private readonly object _timerLock = new object();
        public StateMechine(string stateName)
        {
            _stateName = stateName;
            Mod = stateName;
            _timerEventList = new SortedList<int, Tuple<bool, T2>>();
            _timerTask = TimerTask.GetTimerTaskInstance();
            //_bCreateThread = bCreateThread;
            // _semEvent = new AutoResetEvent(false);
        }
        protected async void Start(T1 initState)
        {
            await Task.Run(() =>
            {
                _curState = initState;
                NotifyStateChange(_curState);
            }).ConfigureAwait(false);
            //   Hlog.I(_stateName,":Start StateMechine");
        }
        /// <summary>
        /// 用于外部启动状态逻辑在这个里面调用私有start 初始化初始状态，单独start 便于 在UI初始化后启动
        /// </summary>
        public abstract void Run();
        private void StateWoker()
        {
            // Interlocked.Exchange(ref _suspendStatet, SUSPEND_NONE);
            Object param = null;
            // _logger?.Debug($"{_stateName}:{_curState} active");
            bool hadNext = false;
            do
            {
                lock (_statelock)
                {
                    hadNext = GetNextEvent(ref _nextEvent, ref param);

                    if (!hadNext)
                    {
                        _suspendStatet = SUSPEND_DONE;
                        break;
                    }
                }
                T1 nextState = DoAction(_nextEvent, param);
                if (!_curState.Equals(nextState))
                {
                    Hlog.I(_stateName, $"{_curState}=>{nextState} taskId:{Thread.CurrentThread.ManagedThreadId}");
                    //ClearEvent();
                    _curState = nextState;
                    NotifyStateChange(_curState);
                }
                ValueTaskCompletionSource<bool> value;
                if (_replyExpectedMsgs.TryGetValue(_nextEvent.GetHashCode(), out value))
                {
                    value.TrySetResult(true);
                }
            } while (true);
            //_logger?.Debug($"{_stateName}:{_curState} suspend");
        }
        /// <summary>
        /// 注册状态机事件处理
        /// </summary>
        /// <param name="state"></param>
        /// <param name="evt"></param>
        /// <param name="action"></param>
        protected void RegisterStateHandle(T1 state, T2 evt, Func<Object, T1> action)
        {
            _stateActions.Add(new Tuple<T1, T2>(state, evt), action);
        }
        /// <summary>
        /// 任何状态收到对应事件都会按照这个处理方法处理，不要和指定状态事件处理冲突
        /// </summary>
        /// <param name="evt"></param>
        /// <param name="action"></param>
        protected void RegisterAllStateHandle(T2 evt, Func<Object, T1> action)
        {
            _globalActions.Add(evt, action);
        }
        private T1 DoAction(T2 nextEvent, Object param)
        {
            Func<Object, T1> action;
            if (_globalActions.TryGetValue(nextEvent, out action))
            {
                T1 preState = _curState;
                Hlog.I(_stateName, $"{_curState}:  do Action : {nextEvent} :" + param?.ToString());
                return action(param);
            }
            if (_stateActions.TryGetValue(new Tuple<T1, T2>(_curState, nextEvent), out action))
            {
                T1 preState = _curState;
                Hlog.I(_stateName, $"{_curState}:  do Action : {nextEvent} :" + param?.ToString());
                return action(param);
            }
            else
            {
                Hlog.W(_stateName, $"{_curState}:  invalid event : {nextEvent}:" + param?.ToString());
                return _curState;
            }
        }

        private void ClearEvent()
        {
            Tuple<T2, object> temp;
            while (_eventQueue.TryDequeue(out temp)) ;
        }
        private bool GetNextEvent(ref T2 evt, ref Object param)
        {
            bool ret = false;
            Tuple<T2, object> pair;
            if (_eventQueue.TryDequeue(out pair))
            {
                evt = pair.Item1;
                param = pair.Item2;
                ret = true;
            }
            return ret;
        }

        public async void PostEventAsync(T2 evt, Object param = null)
        {
            //   Func<Object, T1> action;
            bool waitRun = false;
            //bool excuteFlag = false;
            //_logger?.Warning($"{_stateName}:{_curState}: post event req: {evt}");
            try
            {
                _eventQueue.Enqueue(new Tuple<T2, object>(evt, param));
                //_logger?.Debug("event count:" + _eventQueue.Count);
            }
            catch
            {
                Hlog.W(_stateName, $"{_curState}:  event repeat: {evt}");
                return;
            }
            lock (_statelock)
            {
                if (SusPend)
                {
                    _suspendStatet = SUSPEND_NONE;
                    waitRun = true;
                }
            }
            if (waitRun)
            {
                //_logger?.Debug($"entry StateWoker:{_curState}:  event : {evt}");
                await Task.Run(() => StateWoker()).ConfigureAwait(false);
            }

            // return true;
        }



        public bool PostEvent(T2 evt, Object param, int millisecondsDelay)
        {
            Func<Object, T1> action;
            bool ret = false;
            var token = ValueTaskCompletionSource<bool>.Create();
            int evtId = evt.GetHashCode();
            bool waitRun = false;

            if (!_stateActions.TryGetValue(new Tuple<T1, T2>(_curState, evt), out action)) // 不支持此操作
            {
                if (!_globalActions.TryGetValue(evt, out action)) // 全局事件不支持此操作
                {
                    return false;
                }
            }
            _replyExpectedMsgs[evtId] = token;

            try
            {
                _eventQueue.Enqueue(new Tuple<T2, object>(evt, param));
            }
            catch
            {
                Hlog.W(_stateName, $"{_curState}:  event repeat: {evt}");
                return false;
            }
            lock (_statelock)
            {
                if (SusPend)
                {
                    _suspendStatet = SUSPEND_NONE;
                    waitRun = true;
                }
            }
            if (waitRun)
            {
                Hlog.D(_stateName, $"entry StateWoker:{_curState}:  event : {evt}");
                Task.Run(() => StateWoker()).ConfigureAwait(false);
            }
            Task[] tasks = new Task[2] { token.Task, Task.Delay(millisecondsDelay) };
            if (Task.WhenAny(tasks).Result == token.Task)
            {
                ret = token.Task.Result;
            }
            ValueTaskCompletionSource<bool> value;
            _replyExpectedMsgs.TryRemove((int)evtId, out value);
            return ret;
        }
        /// <summary>
        /// 用来处理进入新状态的初始化，这个过程不允许修改状态，但可以发送事件
        /// </summary>
        /// <param name="state"></param>
        protected abstract void NotifyStateChange(T1 state);
        /// <summary>
        /// 使用该方法是，需要保证初始化执行INI的事件中的逻辑是独立的，避免被多线程干扰
        /// </summary>
        /// <param name="initState"></param>
        protected void StartSync(T1 initState)
        {
            _curState = initState;
            NotifyStateChange(_curState);
        }
        public bool Stop(T2 evt, Object param = null)
        {
            return PostEvent(evt, param, Int32.MaxValue);
        }
        /// <summary>
        /// 专门用来执行延迟执行事件
        /// </summary>
        /// <param name="msecond"></param>
        /// <param name="repeat"></param>
        /// <param name="evt"></param>
        /// <returns></returns>
        public int StartTimer(int msecond, bool repeat, T2 evt)
        {
            int timerId = _timerTask.StartTimer(msecond, repeat, StateTimeoutHandle);
            lock (_timerLock)
            {
                if (timerId != TimerTask.INVALID_TIMER_ID)
                {
                    Tuple<bool, T2> eventItem = new Tuple<bool, T2>(repeat, evt);
                    _timerEventList.Add(timerId, eventItem);
                }
            }
            return timerId;
        }

        private void StateTimeoutHandle(int timerId)
        {
            Tuple<bool, T2> eventItem;
            bool postEvtMsg = false;
            lock (_timerLock)
            {
                if (_timerEventList.TryGetValue(timerId, out eventItem))
                {
                    if (!eventItem.Item1)// repeat task
                    {
                        _timerEventList.Remove(timerId);
                    }
                    postEvtMsg = true;
                    
                }
            }
            if(postEvtMsg)
            {
                PostEventAsync(eventItem.Item2);
            }
        }
        public void StopTimer(ref int timerId)
        {
            lock (_timerLock)
            {
                if (timerId != TimerTask.INVALID_TIMER_ID)
                {
                    _timerTask.StopTimer(ref timerId);
                    _timerEventList.Remove(timerId);
                }
            }
        }

        public void ClearAllTimer()
        {
            lock (_timerLock)
            {
                for (int i = 0; i < _timerEventList.Keys.Count; i++)
                {
                    int timerId = _timerEventList.Keys[i];
                    _timerTask.StopTimer(ref timerId);
                }
                _timerEventList.Clear();
            }
        }
    }
}
