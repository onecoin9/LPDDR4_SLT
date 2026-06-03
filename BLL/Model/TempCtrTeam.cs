using Hsg.Common;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.Model
{


    public enum TempCtrState
    {
        STATE_INIT, //初始状态
        STATE_PREPARE, // 准备状态
                       //STATE_READY,// 就绪状态
        STATE_WORKING,// 工作状态
        STATE_ABNORMAL,// 异常状态
        STATE_EXIT,// 退出状态
    }

    public enum AbnormalCode
    {
        None,
        SndFail,//请求失败
        FanSpeed,//转速不达标
        Voltage,// 工作电压不达标（输出给通讯板）
                /**************dut 状态*****************/
        OverUpLimit,//超出上限
        OverLowerLimit,// 超出下限
        WaitStabilityTimeout,//
    }

    public enum VoltageStage
    {
        Adjusting,// 设置电压
        Checking,// 检查电压
        Ready,// 电压就绪
    }

    public enum TempCtrEvent
    {
        EVT_START_HIGHT_TEMP_MODE,//开启高温模式
        EVT_CONN_CHECK,// 检查通信连接
        EVT_SWITCH_ON_TEMP,
        EVT_SWITCH_OFF_TEMP,
        EVT_SET_TEMP,
        EVT_SET_FAN_SPEED,
        //EVT_VOLTAGE_CHECK,// 检查电压
        EVT_IDLE_HEATBEAT,// 防止掉线待机心跳(用在没开启高温的情况下)
        EVT_CHECK_FAULT,// 检查异常
        EVT_WAIT_STABILITY,// 等待稳定
        EVT_GET_TEMP,
        EVT_GET_FAN_SEPPED,
        EVT_DUTS_STABILITY,// 测试Duts 进入稳定
        EVT_WAIT_TIMEOUT,// 等待稳定超时，停止等待，直接进入工作状态。
        EVT_REFRESH_ABNORMAL,// 刷新异常，（稳定后刷新异常dut）
        EVT_SET_5V_ON_OFF,//设置5V开关
        EVT_5V_ADJUSTING,// 电压调整
        EVT_5V_ADJUSTING_DONE,// 电压调整完成
        EVT_RESET_EVT,// 重置温度设定
        EVT_EXIT,// 退出
    }

    public struct TempDutInfo
    {
        internal int _id;
        private TempCtrState _state;
        public TempCtrState state
        {
            get { return _state; }
            internal set
            {
                if (value != _state)
                {
                    _state = value;
                    _onStateChange?.Invoke(_id, _state, this.value);
                }
            }
        }
        public AbnormalCode StateCode
        {
            get; internal set;
        }
        internal sbyte stateCount;
        private float _value;
        public float value
        {
            get { return _value; }
            internal set
            {
                if (_value != value)
                {
                    _value = value;
                    _onValueChange(_id, value);
                }
            }
        }// 异常值
        internal Action<int, TempCtrState, float> _onStateChange;
        internal Action<int, float> _onValueChange;
        //public TempDutInfo(int id, Action<int, TempCtrState, float> onStateChange)
        //{
        //    _id = id;
        //    _onStateChange += onStateChange;
        //}
    }

    public interface TempCtrTeam
    {

        AbnormalCode StateCode { get; }

        /// <summary>
        /// 进入工作模式
        /// </summary>
        void StartWork();

        /// <summary>
        /// 进入测试模式
        /// </summary>
        void EntryTestMode();

        //  public bool Enable { get { return CurState > TempCtrState.STATE_INIT; } } // 是否开启温控管理
        /// <summary>
        /// 等待环境稳定
        /// </summary>
        void WaitTempStabilityTimeout();

        void Run();
        /// <summary>
        /// 用于测试完成后自动刷新
        /// </summary>
        void ExitTestMode();
        bool CheckEnvIsReady();
       // bool CheckEnvIsAbnormal();
        bool CheckDutEnvReady(int dutId, ref float value);
        void GetFanSpeed(ref ushort[] speeds);

        bool Set5VSwitchOnOff(bool isOn);

        void RsetEnvironment();

        /// <summary>
        /// 通过state code 得到异常
        /// </summary>
        /// <returns></returns>
        string GetStateInfo();
        

        void Exit();

        string GetVoltageInfor();

        /// <summary>
        /// 检查通讯板供电是否就绪
        /// </summary>
        /// <returns></returns>
        bool CheckVoltageIsReady();
        

    }
}
