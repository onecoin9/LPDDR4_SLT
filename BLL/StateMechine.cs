using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
//using System.Collections.Generic;
using Hsg.Common;
namespace Hsg.BLL
{
    /// <summary>
    /// 逻辑处理状态机
    /// </summary>
    /// <typeparam name="T1">stateEnum</typeparam>
    /// <typeparam name="T2">eventNum</typeparam>
     public  abstract  class StateMechine<T1, T2>
    {
        private T1 _curState;
        private T2 _nextEvent;
        private bool _bRunning;
        private List<T2> _msgQueue;
        private Dictionary<Tuple<T1,T2>,Func<T1>> _actionMap;
        private AutoResetEvent _semEvent;
        private object _lockEvent;
        private Thread _thread;
        private string _stateName;
        bool _bCreateThread;// 是否需要单独的线程
        public T1 CurState
        {
            get
            {
                return _curState;
            }
        }

        //   private abstract 
        protected StateMechine(string StateName,bool bCreateThread = true)
        {
            _bRunning = false;
            _msgQueue = new List<T2>();
            _lockEvent = new object();
            _semEvent = new AutoResetEvent(false);
            _actionMap = new Dictionary<Tuple<T1, T2>, Func<T1>>();
            _stateName = StateName;
            _bCreateThread = bCreateThread;
        }
        protected void Start(T1 initState)
        {
            if (!_bRunning)
            {
                _curState = initState;
                NotifyStateChange(_curState);
                if (_bCreateThread)
                {
                    _thread = new Thread(StateWoker);
                    _thread.Start();
                }
            }
            Hlog.D(_stateName, "Start");
        }
        protected void Stop(T1 lastState)
        {
            if (_bRunning)
            {
                if (_bCreateThread)
                {
                    _thread.Abort();
                }
                _bRunning = false;
            }
            //_curState = lastState;
            //NotifyStateChange(_curState);
           // Hlog.D(_stateName, "Stop");
        }
        protected void RegisterStateHandle(T1 state, T2 evt, Func<T1> action)
        {
            Func<T1> checkAction;
            if(!_actionMap.TryGetValue(new Tuple<T1, T2>(state, evt), out checkAction)){
                _actionMap.Add(new Tuple<T1, T2>(state, evt), action);
            }
        }
        protected void PostEvent(T2 evt)
        {
            lock (_lockEvent)
            {
                if (_bCreateThread)
                {
                    _msgQueue.Add(evt);
                    if (_msgQueue.Count == 1)
                    {
                        _semEvent.Set();
                    }
                } else
                {
                    DoAction(evt);
                }
            }
        }
        private bool GetNextEvent(ref T2 evt){
            bool ret = false;
            lock(_lockEvent)
            {
                if (_msgQueue.Count > 0)
                {
                    evt = _msgQueue[0];
                    _msgQueue.RemoveAt(0);
                    ret = true;
                }
            }
            return ret;
        }

        private void DoAction(T2 nextEvent)
        {
            Func<T1> action;
            if (_actionMap.TryGetValue(new Tuple<T1, T2>(_curState, nextEvent), out action))
            {
                T1 preState = _curState;
                Hlog.D(_stateName, _curState + " do Action :" + nextEvent);
                _curState = action();

                if (!_curState.Equals(preState))
                {
                    NotifyStateChange(_curState);
                    Hlog.D(_stateName, "StateChange:" + _curState);
                }
            } else
            {
                Hlog.W(_stateName, _curState + " Invalid Event " + nextEvent);
            }

        }
        private void StateWoker()
        {
            _bRunning = true;
            while (true)
            {
                if (GetNextEvent(ref _nextEvent))
                {
                    DoAction(_nextEvent);
                }
                else
                {
                    _semEvent.WaitOne();
                }
            }
        }

        protected abstract void NotifyStateChange(T1 state);
      
        /// <summary>
        /// 用于上层实现UI界面更新
        /// </summary>
        protected virtual void UpdateUiLayer()
        {

        }
        /// <summary>
        /// 用于外部启动状态逻辑在这个里面调用私有start 初始化初始状态，单独start 便于 在UI初始化后启动
        /// </summary>
        public abstract void Run();
    }
}
