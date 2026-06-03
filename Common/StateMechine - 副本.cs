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
        public bool SusPend
        {
            get { return Interlocked.CompareExchange(ref _suspendStatet, SUSPEND_DONE, SUSPEND_DONE) == SUSPEND_DONE; }
        }
        private readonly ConcurrentDictionary<int,ValueTaskCompletionSource<bool>> _replyExpectedMsgs = new ConcurrentDictionary<int, ValueTaskCompletionSource<bool>>();
        private T1 _curState;
        private T2 _nextEvent;
        private T1 _resumeState;
        protected string _stateName;
        public T1 CurState { get { return _curState; } }
        private readonly object _statelock = new object();
        private readonly object _eventlock = new object();
        private SortedList<T1, List<Func<Task<T1>>>> _subscripStateChangeList = new SortedList<T1, List<Func<Task<T1>>>>();
        private List<Tuple<T2, Object>> _eventList = new List<Tuple<T2, object>>();
        private readonly Dictionary<Tuple<T1, T2>, Func<Object, Task<T1>>> _stateActions = new Dictionary<Tuple<T1, T2>, Func<object, Task<T1>>>();
        protected IHsgLogger _logger;
        public StateMechine(string stateName, IHsgLogger logger)
        {
            _stateName = stateName;
            _logger = logger;
        }
        protected bool start(T1 initState)
        {
            if (SusPend)
            {
                _curState = initState;
                NotifyStateChange(_curState);
                return true;
            }
            _logger?.Debug($"{_stateName}:Start");
            return false;
        }
        /// <summary>
        /// 用于外部启动状态逻辑在这个里面调用私有start 初始化初始状态，单独start 便于 在UI初始化后启动
        /// </summary>
        public abstract void Run();
        private async Task StateWoker()
        {
           // Interlocked.Exchange(ref _suspendStatet, SUSPEND_NONE);
            Object param = null;
            _logger?.Debug($"{_stateName}:{_curState} active");
            bool hadNext = false;
            do
            {
                lock (_statelock)
                {
                    hadNext = GetNextEvent(ref _nextEvent, ref param);
                    if (!hadNext)
                    {
                        Interlocked.Exchange(ref _suspendStatet, SUSPEND_DONE);
                        break;
                    }
                }
                T1 nextState = await DoAction(_nextEvent, param);
                if (!_curState.Equals(nextState))
                {
                    _logger?.Debug($"{_stateName}:{_curState}=>{nextState} taskId:{Thread.CurrentThread.ManagedThreadId}");
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
            _logger?.Debug($"{_stateName}:{_curState} suspend");
        }

        protected void RegisterStateHandle(T1 state, T2 evt, Func<Object, Task<T1>> action)
        {
            _stateActions.Add(new Tuple<T1, T2>(state, evt), action);
        }
        private async Task<T1> DoAction(T2 nextEvent, Object param)
        {
            Func<Object, Task<T1>> action;
            if (_stateActions.TryGetValue(new Tuple<T1, T2>(_curState, nextEvent), out action))
            {
                T1 preState = _curState;
                _logger?.Debug($"{_stateName}:{_curState}:  do Action : {nextEvent}");
                return await action(param);
            }
            else
            {
                _logger?.Warning($"{_stateName}:{_curState}:  invalid event : {nextEvent}");
                return _curState;
            }
        }

        private void ClearEvent()
        {
            lock (_eventlock)
            {
                _eventList.Clear();
            }
        }
        private bool GetNextEvent(ref T2 evt, ref Object param)
        {
            bool ret = false;
            lock (_eventlock)
            {
                foreach (var v in _eventList)
                {
                    
                    evt = v.Item1;
                    param = v.Item2;
                    ret = true;
                    _eventList.Remove(v);
                    break;
                }
                
                
                //if (_eventList.Count > 0)
                //{
                //    evt = _eventList.Values.GetEnumerator;
                //    param = _eventList[0].Item2;
                //    _eventList.RemoveAt(0);
                //    ret = true;
                //}
            }
            return ret;
        }

        public bool PostEventAsync(T2 evt, Object param)
        {
            Func<Object, Task<T1>> action;
            bool waitRun = false;
            //bool excuteFlag = false;
            _logger?.Warning($"{_stateName}:{_curState}: post event req: {evt}");
            if (!_stateActions.TryGetValue(new Tuple<T1, T2>(_curState, evt), out action)) // 不支持此操作
            {
                _logger?.Warning($"{_stateName}:{_curState}:  not support: {evt}");
                return false;
            }
            lock (_eventlock)
            {
                try
                {
                    _eventList.Add(new Tuple<T2, object>(evt, param));
                    _logger?.Debug("event count:" + _eventList.Count);
                }
                catch
                {
                    _logger?.Warning($"{_stateName}:{_curState}:  event repeat: {evt}");
                    return false;
                }
            }
            lock (_statelock)
            {
                if (SusPend)
                {
                    Interlocked.Exchange(ref _suspendStatet, SUSPEND_NONE);
                    waitRun = true;
                }
            }
            if(waitRun)
            {
                _logger?.Debug($"entry StateWoker:{_curState}:  event : {evt}");
                Task.Run(() => StateWoker()).ConfigureAwait(false);
            }

            return true;
        }



        public bool PostEvent(T2 evt, Object param,int millisecondsDelay)
        {
            Func<Object, Task<T1>> action;
            bool ret = false;
            var token = ValueTaskCompletionSource<bool>.Create();
            int evtId = evt.GetHashCode();
            bool waitRun = false;
            if (!_stateActions.TryGetValue(new Tuple<T1, T2>(_curState, evt), out action)) // 不支持此操作
            {
                return false;
            }
            _replyExpectedMsgs[evtId] = token;
           
            lock (_eventlock)
            {
                try
                {
                    _eventList.Add(new Tuple<T2, object>(evt, param));
                }
                catch
                {
                    _logger?.Warning($"{_stateName}:{_curState}:  event repeat: {evt}");
                    return false;
                }
            }
            lock (_statelock)
            {
                if (SusPend)
                {
                    Interlocked.Exchange(ref _suspendStatet, SUSPEND_NONE);
                    waitRun = true;
                }
            }
            if (waitRun)
            {
                _logger?.Debug($"entry StateWoker:{_curState}:  event : {evt}");
                Task.Run(() => StateWoker()).ConfigureAwait(false);
            }
            Task[] tasks = new Task[2] { token.Task, Task.Delay(millisecondsDelay) };
            if ( Task.WhenAny(tasks).Result == token.Task)
            {
                ret = token.Task.Result;
            }
            ValueTaskCompletionSource<bool> value;
            _replyExpectedMsgs.TryRemove((int)evtId, out value);
            return ret;
        }

        internal virtual void NotifyStateChange(T1 state) { }
        public void Start(T1 initState)
        {
            _curState = initState;
            NotifyStateChange(_curState);
        }
        public bool Stop(T2 evt, Object param)
        {
            return PostEventAsync(evt, param);
        }

        //public void SubscriptStateChange(T1 state, Func<Task<T1>> action)
        //{
        //    List<Func<Task<T1>>> actionList = null;
        //    if (!_subscripStateChangeList.TryGetValue(state, out actionList))
        //    {
        //        actionList = new List<Func<Task<T1>>>();
        //        _subscripStateChangeList.Add(state, actionList);
        //    }
        //    if (!actionList.Contains(action))
        //    {
        //        actionList.Add(action);
        //    }
        //}
        //public void UnsubscribeStateChange(T1 state, Func<Task<T1>> action)
        //{
        //    List<Func<Task<T1>>> actionList = null;
        //    if (_subscripStateChangeList.TryGetValue(state, out actionList))
        //    {
        //        actionList.Remove(action);
        //    }
        //}
    }
}
