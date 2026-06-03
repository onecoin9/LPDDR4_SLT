using Hsg.Common;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Hsg.ViewModel
{
    public class BSMainViewModel : INotifyPropertyChanged
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

        private string _orderNumber;
        /// <summary>
        /// 订单编号
        /// </summary>
        public string OrderNumber
        {
            get
            {
                return _orderNumber;
            }
            set
            {
                if (value != _orderNumber)
                {
                    _orderNumber = value;
                    OnUiPropertyChanged(nameof(OrderNumber));
                }
            }
        }

        private string _materialNumber;
        /// <summary>
        /// 物料编号
        /// </summary>
        public string MaterialNumber
        {
            get
            {
                return _materialNumber;
            }
            set
            {
                if (value != _materialNumber)
                {
                    _materialNumber = value;
                    OnUiPropertyChanged(nameof(MaterialNumber));
                }
            }
        }

        private string _testStatistics;
        /// <summary>
        /// 测试统计
        /// </summary>
        public string TestStatistics
        {
            get
            {
                return _testStatistics;
            }
            set
            {
                if (value != _testStatistics)
                {
                    _testStatistics = value;
                    OnUiPropertyChanged(nameof(TestStatistics));
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
                if (_serviceStart!= value)
                {
                    _serviceStart = value;
                    OnUiPropertyChanged(nameof(ServiceState));
                }
                
            }
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
                return _onlineBoard.ToString() + "/64";
            }
        }


        private string _emiName;
        public string EmiName
        {
            get
            {
                return _emiName;
            }
            set
            {
                if(_emiName!= value)
                {
                    _emiName = value;
                }
                OnUiPropertyChanged(EmiName);
            }
        }



        public event PropertyChangedEventHandler PropertyChanged;
        protected virtual void OnUiPropertyChanged(string propertyName)
        {
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
            _workTime = "00:00:01";
            _orderNumber = "XXXXXXXXXXX";
            _materialNumber = "XXXXXXXXXXX";
            _testStatistics = "0/0";
            _handlerServerConnState = ConnState.DISCONNECT;
            _serviceStart = false;
            _onlineBoard = 0;
            _emiName = "";
        }
        public async void Test()
        {
            DateTime start = DateTime.Now;

            await Task.Run(async () =>
            {
                while (true)
                {
                    //await Task.Delay(2000);
                    //TimeSpan span = DateTime.Now - start;
                    //int totalHours = (int)span.TotalHours; // 获取总小时数
                    //int minutes = span.Minutes;
                    //int seconds = span.Seconds;
                    //TimeCount = $"{totalHours:D2}:{minutes:D2}:{seconds:D2}";
                    //int state = (int)_stage;
                    //if (state <= (int)TestStage.ST_TEST_TIMEOUT)
                    //{
                    //    state++;
                    //}
                    //else
                    //{
                    //    state = (int)TestStage.ST_NOT_START;
                    //}
                    //Stage = (TestStage)state;
                    //for (int i = 0; i < _dutStates.Length; i++)
                    //{
                    //    _dutStates[i] = Stage;
                    //}
                    //BoardBIsReady = BoardAIsReady;
                    //BoardAIsReady = !BoardBIsReady;
                }
            });
        }
        private void OnDutStateChange(int index)
        {
            OnUiPropertyChanged("Dut" + (index + 1).ToString() + "Color");
        }

    }
}
