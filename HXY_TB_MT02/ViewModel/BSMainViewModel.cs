using Hsg.Common;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Hsg.BLL.ViewModel;
using Hsg.BLL;

namespace Hsg.View
{
    public class BSMainViewModel : IBSViewModel, INotifyPropertyChanged
    {
        private readonly SynchronizationContext _synchronizationContext = SynchronizationContext.Current; // 假设这是在 UI 线程上初始化的

        private string _workTime;
        /// <summary>
        /// 测试时间
        /// </summary>
        public string WorkTime
        {
            get { return _workTime; }
            set
            {
                if (_workTime != value)
                {
                    _workTime = value;
                    OnUiPropertyChanged(nameof(WorkTime));
                }
            }
        }




        private ConnState _handlerServerConnState;
        /// <summary>
        /// Handle server connect state
        /// </summary>
        public ConnState HandleServerConnState
        {
            get
            {
                return _handlerServerConnState;
            }
            set
            {
                if (_handlerServerConnState != value)
                {
                    _handlerServerConnState = value;
                    OnUiPropertyChanged(nameof(HanderServerState));
                }
            }
        }
        /// <summary>
        /// Handle server通讯状态
        /// </summary>
        public String HanderServerState
        {
            get
            {
                if (_handlerServerConnState == ConnState.CONNECTED)
                {
                    return "通讯连接";
                }
                else
                {
                    return "通讯断开";
                }
            }
        }


        private bool _serviceStart;
        /// <summary>
        /// 给model 使用
        /// </summary>
        public bool ServiceStart
        {
            get
            {
                return _serviceStart;
            }
            set
            {
                if (_serviceStart != value)
                {
                    _serviceStart = value;
                    OnUiPropertyChanged(nameof(ServiceEnableStart));
                    OnUiPropertyChanged(nameof(ServiceEnablePause));
                }
            }
        }

        public bool ServiceEnableStart
        {
            get { return !_serviceStart & _serviceReady; }
        }
        public bool ServiceEnablePause
        {
            get { return _serviceStart; }
        }
        /// <summary>
        /// 测试服务是否开启
        /// </summary>
        public string ServiceState
        {
            get
            {
                if (_serviceStart)
                {
                    return "服务开启";
                }
                else
                {
                    return "服务关闭";
                }
            }
        }

        //  private bool _isDebugMode;
        public string WorkMode
        {
            get
            {
                switch (SysConfig.WorkMode)
                {
                    case Common.WorkMode.Debug:
                        return "调试模式";
                    case Common.WorkMode.Online:
                        return "云端模式";
                    case Common.WorkMode.Slave:
                        return "从机模式";
                    case Common.WorkMode.OffLine:
                        return "本地模式";
                    default:
                        return "异常模式";
                }
            }
        }

        private int _onlineBoard;
        /// <summary>
        /// 给model 使用
        /// </summary>
        public int OnlineBoard
        {
            get
            {
                return _onlineBoard;
            }
            set
            {
                if (_onlineBoard != value)
                {
                    _onlineBoard = value;
                    OnUiPropertyChanged(nameof(OnlineBoardStatistics));
                }

            }
        }
        /// <summary>
        /// 在线通信版统计
        /// </summary>
        public string OnlineBoardStatistics
        {
            get
            {
                return _onlineBoard.ToString() + "/" + SysConfig.DEV_NUM;
            }
        }


        private string _policyName;
        public string PolicyName
        {
            get
            {
                return _policyName;
            }
            set
            {
                if (_policyName != value)
                {
                    _policyName = value;
                }
                OnUiPropertyChanged(PolicyName);
            }
        }

        public int TestingTeamNum { get; set; }

        private int _passDutNum;
        public int PassDutNum
        {
            get { return _passDutNum; }
            set
            {
                if (_passDutNum != value)
                {
                    _passDutNum = value;
                    OnUiPropertyChanged(nameof(TestStatistics));
                }
            }
        }

        private int _testDutNum;
        public int TestDutNum
        {
            get { return _testDutNum; }
            set
            {
                if (_testDutNum != value)
                {
                    _testDutNum = value;
                    OnUiPropertyChanged(nameof(TestStatistics));
                }
            }
        }

        /// <summary>
        /// 测试统计
        /// </summary>
        public string TestStatistics
        {
            get
            {
                if (TestDutNum > 0)
                {
                    return $"{_passDutNum}/{_testDutNum}" + "(" + (100 * (float)PassDutNum / (float)TestDutNum).ToString("F2") + "%)";
                }
                else
                {
                    return "0/0";
                }
            }

        }

        public bool ViewEnable { get; set; }

        private bool _serviceReady;
        public bool ServiceReady
        {
            get
            {
                return _serviceReady;
            }

            set
            {
                if (_serviceReady != value)
                {
                    _serviceReady = value;
                    OnUiPropertyChanged("ServiceEnableStart");
                };
            }
        }

        public event PropertyChangedEventHandler PropertyChanged;
        protected virtual void OnUiPropertyChanged(string propertyName)
        {
            if (!ViewEnable)
            {
                return;
            }
            _synchronizationContext.Post(state =>
            {
                // 假设这里有一些 UI 相关的更新
                PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
            }, null);

        }
        public BSMainViewModel()
        {
            //State = "等待开始";
            //   StateColor = System.Drawing.Color.Lime;
            _workTime = "00:00:00";
            //_orderNumber = "XXXXXXXXXXX";
            //_materialNumber = "XXXXXXXXXXX";
            _handlerServerConnState = ConnState.DISCONNECT;
            _serviceStart = false;
            _onlineBoard = 0;
            _policyName = "";
            ViewEnable = true;
        }
        public void Test()
        {

        }
    }
}
