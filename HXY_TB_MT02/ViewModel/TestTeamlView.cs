using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Hsg.Common;
using Hsg.BLL.ViewModel;
using Hsg.BLL;

namespace Hsg.View
{

    public class TestTeamlView : INotifyPropertyChanged, ITeamViewModel
    {
        //private  Color[] BackColorList;
        //private Color[] _dutForeColorList;

        private readonly SynchronizationContext _synchronizationContext = SynchronizationContext.Current; // 假设这是在 UI 线程上初始化的
        public string Id;
        private string _TimeCount = "00:00:00";
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
                        return Color.Gray;
                    case TestStage.ST_PREPARE:
                        return Color.LimeGreen;
                    case TestStage.ST_READY:
                        return Color.LimeGreen;
                    case Common.TestStage.ST_TESTING:
                        return Color.LimeGreen;
                    case Common.TestStage.ST_TEST_FAIL:
                        return Color.Red;
                    case Common.TestStage.ST_TEST_TIMEOUT:
                        return Color.Red;
                    case Common.TestStage.ST_TEST_SUCCESS:
                        return Color.LimeGreen;
                    default:
                        return Color.LimeGreen;
                }
            }
        }
        public string StateDescript
        {
            get
            {
                switch (_stage)
                {
                    case TestStage.ST_NOT_START:
                        return "设备脱管";
                    case TestStage.ST_PREPARE:
                        return "准备中...";
                    case TestStage.ST_READY:
                        if(WorkModeOpen)
                        {
                            return "待测试";
                        }
                        if(!GroupReady[0]|| !GroupReady[1])
                        {
                            return "部分就绪";
                        }
                        return "准备就绪";
                    case TestStage.ST_TESTING:
                        return "R." + TestStageDescript;
                    case TestStage.ST_TEST_FAIL:
                        return "测试失败";
                    case TestStage.ST_TEST_TIMEOUT:
                        return "测试超时";
                    case TestStage.ST_TEST_SUCCESS:
                        return "测试完成";
                    default:
                        return "设备脱管";

                }
            }
        }
        private int DUT_COUNT = SysConfig.TEAM_GROUP_NUM * SysConfig.PORT_NUM;

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

        public ObservableArray<bool> GroupReady { get; set; }

        public Color BoardAColor
        {
            get
            {
                if (GroupReady[0])
                {
                    return Color.Green;
                }
                else
                {
                    return Color.Red;
                }
            }
        }

        public Color BoardBColor
        {
            get
            {
                if (GroupReady[1])
                {
                    return Color.Green;
                }
                else
                {
                    return Color.Red;
                }
            }
        }

        public short TempValue1
        {
            get
            {
                return DutTemps[0];
            }
        }
        public short TempValue2
        {
            get
            {
                return DutTemps[1];
            }
        }
        public short TempValue3
        {
            get
            {
                return DutTemps[2];
            }
        }
        public short TempValue4
        {
            get
            {
                return DutTemps[3];
            }
        }
        public short TempValue5
        {
            get
            {
                return DutTemps[4];
            }
        }
        public short TempValue6
        {
            get
            {
                return DutTemps[5];
            }
        }
        public short TempValue7
        {
            get
            {
                return DutTemps[6];
            }
        }
        public short TempValue8
        {
            get
            {
                return DutTemps[7];
            }
        }
        public short TempValue9
        {
            get
            {
                return DutTemps[8];
            }
        }
        public short TempValue10
        {
            get
            {
                return DutTemps[9];
            }
        }

        public short TempValue11
        {
            get
            {
                return DutTemps[10];
            }
        }

        public short TempValue12
        {
            get
            {
                return DutTemps[11];
            }
        }
        public short TempValue13
        {
            get
            {
                return DutTemps[12];
            }
        }
        public short TempValue14
        {
            get
            {
                return DutTemps[13];
            }
        }
        public short TempValue15
        {
            get
            {
                return DutTemps[14];
            }
        }
        public short TempValue16
        {
            get
            {
                return DutTemps[15];
            }
        }
        public short TempValue17
        {
            get
            {
                return DutTemps[16];
            }
        }
        public short TempValue18
        {
            get
            {
                return DutTemps[17];
            }
        }
        public short TempValue19
        {
            get
            {
                return DutTemps[18];
            }
        }
        public short TempValue20
        {
            get
            {
                return DutTemps[19];
            }
        }
        public short TempValue21
        {
            get
            {
                return DutTemps[20];
            }
        }
        public short TempValue22
        {
            get
            {
                return DutTemps[21];
            }
        }
        public short TempValue23
        {
            get
            {
                return DutTemps[22];
            }
        }
        public short TempValue24
        {
            get
            {
                return DutTemps[23];
            }
        }


        public int TeamId { get; set; }

        public ObservableArray<StringBuilder> DutsDetail { get; set; }


        public ObservableArray<string> GroupDetail { get; set; }


        public StringBuilder TeamDetail { get; set; }

        private bool _workModeOpen;
        public bool WorkModeOpen
        {
            get { return _workModeOpen; }
            set
            {
                if (_workModeOpen != value)
                {
                    _workModeOpen = value;
                    OnUiPropertyChanged(nameof(StateDescript));
                }
            }
        }

        public bool ViewEnable { get; set; }

        private bool _abnormalFlag;
        public bool AlarmFlag
        {
            get { return _abnormalFlag; }
            set
            {
                if (_abnormalFlag!= value)
                {
                    _abnormalFlag = value;
                    OnUiPropertyChanged(nameof(TeamAbnormalColor));
                }
             } 
        }
        public string AlarmMsg { get; set; }

        private string _alramCountdown;
        public string AlarmCountdown
        {
            get { return _alramCountdown; }
            set
            {
                if(value != _alramCountdown)
                {
                    _alramCountdown = value;
                    OnUiPropertyChanged(nameof(AlarmCountdown));
                }
            }
        }
		
		 private int _policyTestTotalStage = 0;
        public int PolicyTestTotalStage
        {
            get { return _policyTestTotalStage; }
            set
            {
                _policyTestTotalStage = value;
                OnUiPropertyChanged(nameof(StateDescript));
            }
        }// 配方总阶段数
        private int _policyTestCurStage = -1;
        public int PolicyTestCurStage
        {
            get { return _policyTestCurStage; }
            set
            {
                _policyTestCurStage = value;
                OnUiPropertyChanged(nameof(StateDescript));
            }
        }// 配方总阶段数

        public int _excuteCount
        {
            get; set;
        }
        public int ExcuteCount
        {
            get { return _excuteCount; }
            set
            {
                _excuteCount = value;
                OnUiPropertyChanged(nameof(StateDescript));
            }
        }

        public string TestStageDescript
        {
            get { return $"{PolicyTestTotalStage}-{PolicyTestCurStage + 1} T{ExcuteCount}"; }

        }// 策略测试阶段

        public ObservableArray<short> DutTemps { get; set; }
        

        public event PropertyChangedEventHandler PropertyChanged;
        protected virtual void OnUiPropertyChanged(string propertyName)
        {
            if(!ViewEnable)
            {
                return;
            }
            _synchronizationContext.Post(state =>
            {
                // 假设这里有一些 UI 相关的更新
                PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
            }, null);
        }
        public TestTeamlView()
        {
            Id = "0";
            //TimeCount = "00:00:01";
            TeamDetail = new StringBuilder();
            DutStates = new ObservableArray<TestStage>(new TestStage[DUT_COUNT]);
            DutStates.OnArrayChange += OnDutStateChange;
            GroupReady = new ObservableArray<bool>(new bool[] { false, false });
            GroupReady.OnArrayChange += OnGroupStateChange;
            StringBuilder[] dutsDetailInit = new StringBuilder[DUT_COUNT];
            for (int i = 0; i < dutsDetailInit.Length; i++)
            {
                dutsDetailInit[i] = new StringBuilder();
            }
            DutsDetail = new ObservableArray<StringBuilder>(dutsDetailInit);

            string[] groupDetailInit = new string[SysConfig.TEAM_GROUP_NUM];
            for (int i = 0; i < groupDetailInit.Length; i++)
            {
                groupDetailInit[i] = string.Empty;
            }
            GroupDetail = new ObservableArray<string>(groupDetailInit);

            DutTemps = new ObservableArray<short>(new short[DUT_COUNT]);
            DutTemps.OnArrayChange += OnTempValueChange;
            ViewEnable = true;
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
                    await Task.Delay(5000);
                    TimeSpan span = DateTime.Now - start;
                    int totalHours = (int)span.TotalHours; // 获取总小时数
                    int minutes = span.Minutes;
                    int seconds = span.Seconds;
                    TimeCount = $"{totalHours:D2}:{minutes:D2}:{seconds:D2}";
                    int state = (int)_stage;
                    if (state < (int)TestStage.ST_TEST_TIMEOUT)
                    {
                        state++;
                    }
                    else
                    {
                        state = (int)TestStage.ST_NOT_START;
                    }
                    Stage = (TestStage)state;
                    for (int i = 0; i < DutStates.Length; i++)
                    {
                        DutStates[i] = Stage;
                    }
                }
            });
        }
        private void OnDutStateChange(int index, object param)
        {
            OnUiPropertyChanged("Dut" + (index + 1).ToString() + "Color");
        }


        private void OnGroupStateChange(int index, object param)
        {
            switch (index)
            {
                case 0:
                    OnUiPropertyChanged("BoardAColor");
                    break;
                case 1:
                    OnUiPropertyChanged("BoardBColor");
                    break;
            }
        }

        private void OnTempValueChange(int index, object param)
        {
            int tempId = index + 1;
            OnUiPropertyChanged("Temp" + nameof(tempId));
        }
        private Color GetDutStateColor(int dutId)
        {
            //if(dutId <4)
            //{
            //    return Color.Red;
            //}else if(dutId <8) { 
            //    return Color.Green;
            //} else if (dutId <12)
            //{
            //    return Color.Purple;
            //} else if(dutId <16)
            //{
            //    return Color.Blue;
            //} else if(dutId<20)
            //{
            //    return Color.OrangeRed;
            //} else if(dutId <24)
            //{
            //    return Color.Violet;
            //}
            TestStage state = DutStates[dutId];
            switch (state)
            {
                case TestStage.ST_NOT_START:
                case TestStage.ST_PREPARE:
                    //return Color.Gray;
                    return SystemColors.WindowFrame;
                // return Color.DarkGray;
                //return Color.Violet;
                case TestStage.ST_TESTING:
                    // return Color.Gold;
                    // return Color.Olive;
                    return Color.Goldenrod;
                case TestStage.ST_TEST_FAIL:
                case TestStage.ST_TEST_TIMEOUT:
                    return Color.Red;
                case TestStage.ST_TEST_SUCCESS:
                    return Color.Green;
                default:
                    return Color.Gray;
            }
        }

        public Color TeamAbnormalColor
        {
            get
            {
               if(AlarmFlag)
                {
                    return Color.Red;
                }
                else
                {
                    return Color.FromArgb(30, 35, 126);
                }
            }
        }
    }
}
