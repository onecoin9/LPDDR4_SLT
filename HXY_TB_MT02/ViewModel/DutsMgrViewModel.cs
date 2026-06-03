using Hsg.BLL;
using Hsg.BLL.ViewModel;
using Hsg.Common;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Hsg.View.ViewModel
{
    class DutsMgrViewModel: IDutsMgrViewModel,INotifyPropertyChanged
    {
        private readonly SynchronizationContext _synchronizationContext = SynchronizationContext.Current; // 假设这是在 UI 线程上初始化的
        private TestStage _stage;
        public TestStage Stage
        {
            get
            {
                return _stage;
            }
            set
            {
                if (_stage != value)
                {
                    _stage = value;
                    OnUiPropertyChanged(nameof(StateDescript));
                }
            }
        }
        public Color StateColor
        {
            get
            {
                switch (_stage)
                {
                    case Common.TestStage.ST_NOT_START:
                        return Color.Red;
                    case TestStage.ST_PREPARE:
                        return Color.Lime;
                    case TestStage.ST_READY:
                        return Color.Lime;
                    case Common.TestStage.ST_TESTING:
                        return Color.Lime;
                    case Common.TestStage.ST_TEST_FAIL:
                        return Color.Red;
                    case Common.TestStage.ST_TEST_TIMEOUT:
                        return Color.Red;
                    case Common.TestStage.ST_TEST_SUCCESS:
                        return Color.Lime;
                    default:
                        return Color.Lime;

                }
            }
        }
        public string StateDescript
        {
            get
            {
                switch (_stage)
                {
                    case Common.TestStage.ST_NOT_START:
                        return "设备脱管";
                    case TestStage.ST_PREPARE:
                        return "准备中...";
                    case TestStage.ST_READY:
                        return "准备就绪";
                    case Common.TestStage.ST_TESTING:
                        return "测试中...";
                    case Common.TestStage.ST_TEST_FAIL:
                        return "测试失败";
                    case Common.TestStage.ST_TEST_TIMEOUT:
                        return "测试超时";
                    case Common.TestStage.ST_TEST_SUCCESS:
                        return "测试完成";
                    default:
                        return "设备脱管";

                }
            }
        }

        public ObservableArray<TestStage> DutStates { get; set; }
        public Color Dut1Color
        {
            get
            {
                return GetDutStateColor(0);
            }
        }
        public Color Dut2Color
        {
            get
            {
                return GetDutStateColor(1);
            }
        }
        public Color Dut3Color
        {
            get
            {
                return GetDutStateColor(2);
            }
        }
        public Color Dut4Color
        {
            get
            {
                return GetDutStateColor(3);
            }
        }
        public Color Dut5Color
        {
            get
            {
                return GetDutStateColor(4);
            }
        }
        public Color Dut6Color
        {
            get
            {
                return GetDutStateColor(5);
            }
        }
        public Color Dut7Color
        {
            get
            {
                return GetDutStateColor(6);
            }
        }
        public Color Dut8Color
        {
            get
            {
                return GetDutStateColor(7);
            }
        }
        public Color Dut9Color
        {
            get
            {
                return GetDutStateColor(8);
            }
        }
        public Color Dut10Color
        {
            get
            {
                return GetDutStateColor(9);
            }
        }
        public Color Dut11Color
        {
            get
            {
                return GetDutStateColor(10);
            }
        }
        public Color Dut12Color
        {
            get
            {
                return GetDutStateColor(11);
            }
        }

        private bool _boardIsReady;
        public bool BoardIsReady
        {
            get { return _boardIsReady; }
            set
            {
                if (_boardIsReady != value)
                {
                    _boardIsReady = value;
                    OnUiPropertyChanged(nameof(BoardColor));
                }
            }
        }
        public Color BoardColor
        {
            get
            {
                if (BoardIsReady)
                {
                    return Color.Green;
                }
                else
                {
                    return Color.Red;
                }
            }
        }
        private bool _boardBIsReady;
      
        public int TeamId { get; }
        public int GroupId { get; }


        public event PropertyChangedEventHandler PropertyChanged;
        protected virtual void OnUiPropertyChanged(string propertyName)
        {
            _synchronizationContext.Post(state =>
            {
                // 假设这里有一些 UI 相关的更新
                PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
            }, null);

        }
        public DutsMgrViewModel(int teamId, int groupId)
        {
            TeamId = teamId;
            GroupId = groupId;
            DutStates = new ObservableArray<TestStage>(new TestStage[SysConfig.PORT_NUM]);
            DutStates.OnArrayChange += OnDutStateChange;
            //State = "等待开始";
            //   StateColor = System.Drawing.Color.Lime;
        }
        //public async void Test()
        //{
        //    DateTime start = DateTime.Now;

        //    await Task.Run(async () =>
        //    {
        //        while (true)
        //        {
        //            await Task.Delay(5000);
        //            TimeSpan span = DateTime.Now - start;
        //            int totalHours = (int)span.TotalHours; // 获取总小时数
        //            int minutes = span.Minutes;
        //            int seconds = span.Seconds;
        //            TimeCount = $"{totalHours:D2}:{minutes:D2}:{seconds:D2}";
        //            int state = (int)_stage;
        //            if (state < (int)TestStage.ST_TEST_TIMEOUT)
        //            {
        //                state++;
        //            }
        //            else
        //            {
        //                state = (int)TestStage.ST_NOT_START;
        //            }
        //            Stage = (TestStage)state;
        //            for (int i = 0; i < DutStates.Length; i++)
        //            {
        //                DutStates[i] = Stage;
        //            }
        //            BoardBIsReady = BoardAIsReady;
        //            BoardAIsReady = !BoardBIsReady;
        //        }
        //    });
        //}
        private void OnDutStateChange(int index)
        {
            OnUiPropertyChanged("Dut" + (index + 1).ToString() + "Color");
        }
        private Color GetDutStateColor(int dutId)
        {
            TestStage state = DutStates[dutId];
            switch (state)
            {
                case TestStage.ST_NOT_START:
                case TestStage.ST_PREPARE:
                    return Color.Gray;
                //return Color.Violet;
                case TestStage.ST_TESTING:
                    return Color.Gold;
                case TestStage.ST_TEST_FAIL:
                case TestStage.ST_TEST_TIMEOUT:
                    return Color.Red;
                case TestStage.ST_TEST_SUCCESS:
                    return Color.Green;
                default:
                    return Color.Gray;
            }
        }

    }
}
