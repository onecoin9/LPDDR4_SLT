using Hsg.Common;
using System;
using System.Text;

namespace Hsg.BLL.ViewModel
{
    public interface ITeamViewModel
    {
        int TeamId { get; set; }

        string TimeCount { get; set; }
        //TestStage Stage { get; set; }
        //bool BoardIsReady { get; set; }

        bool WorkModeOpen { get; set; }
        TestStage Stage { get; set; }
        ///// <summary>
        ///// Group测试状态
        ///// </summary>
        //ObservableArray<TestStage> GroupStates { get; set; }
        /// <summary>
        /// 测试状态
        /// </summary>
        ObservableArray<TestStage> DutStates { get; set; }
        /// <summary>
        /// dut 测试详情
        /// </summary>
        ObservableArray<StringBuilder> DutsDetail { get; set; }

        ObservableArray<short> DutTemps { get; set; }
        /// <summary>
        /// 通讯板的测试详情
        /// </summary>
        ObservableArray<string> GroupDetail { get; set; }
        StringBuilder TeamDetail { get; set; }
        ObservableArray<bool> GroupReady { get; set; }
        /// <summary>
        /// 是否UI控件已经绘制
        /// </summary>
        bool ViewEnable { get; set; }
        /// <summary>
        /// 是否存在异常，报警
        /// </summary>
        bool AlarmFlag { get; set; }
        string AlarmMsg { get; set; }
        string AlarmCountdown { get; set; }
        //ObservableArray<TestStage> DutsMgrState { get; set; }
        int PolicyTestTotalStage { get; set; }// 配方总阶段数
        int PolicyTestCurStage { get; set; }// 当前配方阶段
        int ExcuteCount { get; set; }//当前执行次数
    }
}
