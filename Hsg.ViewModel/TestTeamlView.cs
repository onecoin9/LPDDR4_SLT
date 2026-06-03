using System;
using System.ComponentModel;
using System.Threading;
using System.Threading.Tasks;
using Hsg.Common;
namespace Hsg.ViewModel
{

    public class TestTeamlView : INotifyPropertyChanged
    {
        //private  Color[] BackColorList;
        //private Color[] _dutForeColorList;

        private readonly SynchronizationContext _synchronizationContext = SynchronizationContext.Current; // 假设这是在 UI 线程上初始化的
        public string Id;
        private string _TimeCount;
        public string TimeCount
        {
            get { return _TimeCount; }
            set
            {
                if (_TimeCount != value)
                {
                    _TimeCount = value;
                    OnUiPropertyChanged(nameof(TimeCount));
                }
            }
        }


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
        private int DUT_COUNT = 24;

        public ObservableArray<TestStage> _dutStates;
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
        public Color Dut13Color
        {
            get
            {
                return GetDutStateColor(12);
            }
        }
        public Color Dut14Color
        {
            get
            {
                return GetDutStateColor(13);
            }
        }
        public Color Dut15Color
        {
            get
            {
                return GetDutStateColor(14);
            }
        }
        public Color Dut16Color
        {
            get
            {
                return GetDutStateColor(15);
            }
        }
        public Color Dut17Color
        {
            get
            {
                return GetDutStateColor(16);
            }
        }
        public Color Dut18Color
        {
            get
            {
                return GetDutStateColor(17);
            }
        }
        public Color Dut19Color
        {
            get
            {
                return GetDutStateColor(18);
            }
        }
        public Color Dut20Color
        {
            get
            {
                return GetDutStateColor(19);
            }
        }
        public Color Dut21Color
        {
            get
            {
                return GetDutStateColor(20);
            }
        }
        public Color Dut22Color
        {
            get
            {
                return GetDutStateColor(21);
            }
        }
        public Color Dut23Color
        {
            get
            {
                return GetDutStateColor(22);
            }
        }
        public Color Dut24Color
        {
            get
            {
                return GetDutStateColor(23);
            }
        }

        private bool _boardAIsReady;
        public bool BoardAIsReady
        {
            get { return _boardAIsReady; }
            set
            {
                if (_boardAIsReady != value)
                {
                    _boardAIsReady = value;
                    OnUiPropertyChanged(nameof(BoardAColor));
                }
            }
        }
        public Color BoardAColor
        {
            get
            {
                if(BoardAIsReady)
                {
                    return Color.Green;
                }else
                {
                    return Color.Red;
                }
            }
        }
        private bool _boardBIsReady;
        public bool BoardBIsReady
        {
            get { return _boardBIsReady; }
            set
            {
                if(_boardBIsReady != value)
                {
                    _boardBIsReady = value;
                    OnUiPropertyChanged(nameof(BoardBColor));
                }
            }
        }
        public Color BoardBColor
        {
            get
            {
                if (BoardBIsReady)
                {
                    return Color.Green;
                }
                else
                {
                    return Color.Red;
                }
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
        public TestTeamlView()
        {
            Id = "1";
            TimeCount = "00:00:01";
            _dutStates = new ObservableArray<TestStage>(new TestStage[DUT_COUNT]);
            _dutStates.OnArrayChange += OnDutStateChange;
            //State = "等待开始";
            //   StateColor = System.Drawing.Color.Lime;
        }
        public async void Test()
        {
            DateTime start = DateTime.Now;

            await Task.Run(async () =>
            {
                while (true)
                {
                    await Task.Delay(2000);
                    TimeSpan span = DateTime.Now - start;
                    int totalHours = (int)span.TotalHours; // 获取总小时数
                    int minutes = span.Minutes;
                    int seconds = span.Seconds;
                    TimeCount = $"{totalHours:D2}:{minutes:D2}:{seconds:D2}";
                    int state = (int)_stage;
                    if (state <= (int)TestStage.ST_TEST_TIMEOUT)
                    {
                        state++;
                    }
                    else
                    {
                        state = (int)TestStage.ST_NOT_START;
                    }
                    Stage = (TestStage)state;
                    for (int i = 0; i < _dutStates.Length; i++)
                    {
                        _dutStates[i] = Stage;
                    }
                    BoardBIsReady = BoardAIsReady;
                    BoardAIsReady = !BoardBIsReady;
                }
            });
        }
        private void OnDutStateChange(int index)
        {
            OnUiPropertyChanged("Dut" + (index + 1).ToString() + "Color");
        }
        private Color GetDutStateColor(int dutId)
        {
            TestStage state = _dutStates[dutId];
            switch (state)
            {
                case TestStage.ST_NOT_START:
                case TestStage.ST_PREPARE:
                    return Color.Gray;
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
