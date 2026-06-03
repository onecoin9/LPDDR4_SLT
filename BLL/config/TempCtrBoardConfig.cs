using Hsg.Common;
using Hsg.Common.ADO;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.config
{
    public class TempCtrBoardConfig
    {
        private int _instanceId;
        private SysConfig _sysConfig;
        public string IP = "127.0.0.1";
        public ushort[] Ports;
        private float _targetTemp;
        public static int DUTS_COUNT = SysConfig.PORT_NUM * SysConfig.TEAM_GROUP_NUM;
        public float TargetTemp { get { return _targetTemp; } }
        private float _tempCompensator;
        public float DefaultTempCompensator { get { return _tempCompensator; } }// 温度补偿
        private Int16 _targetSpeed;
        public Int16 TargetSpeed { get { return _targetSpeed; } }// 风扇速度 1-100
        private ushort _speedLowerLimit;
        public ushort SpeedLowerLimit { get { return _speedLowerLimit; } }
        public float WorkTempHight { get { return TargetTemp + TempMistack; } } // 工作温度上限
        public float WorkTempLow { get { return TargetTemp - TempMistack; } }// 工作温度下限
        public float NormalTempHight { get; } // 常温上限
        private float _tempMistake;
        public float TempMistack
        {
            get { return _tempMistake; }
        }
        private float[] _dutsTempCompensator;
        /// <summary>
        /// 温度补偿
        /// </summary>
        public float[] DutsTempCompensator
        {
            get { return _dutsTempCompensator; }
        }

        public bool TempCtrInitAllEnable
        {
            get { return _sysConfig.TempCtrInitAllEnable.CheckBoolValue(); }
        }

        private bool _useDiffCompensator;// 使用差别补偿
        public bool UseDiffCompensator
        {
            get { return _useDiffCompensator; }
        }

        public float AttenuationValue// 衰减值(实际显示只= 读取值-衰减值）
        {
            get { return _tempCompensator; }
        }
        public bool NormalTempCheck
        {
            get;
        }
        public float OutWorkVoltage { get; }

        public float VoltageCloseThreshold { get; }

        public float GetDutTempCompensator(int dutId)
        {
            if (dutId >= 0 && dutId < SysConfig.TEAM_GROUP_NUM * SysConfig.PORT_NUM && dutId < _dutsTempCompensator.Length)
            {
                return _dutsTempCompensator[dutId];
            }
            return DefaultTempCompensator;
        }

        public bool OpenTempMgr
        {
            get { return SysConfig.TempState == (byte)TempState.TmpHight || SysConfig.TempState == (byte)TempState.TmpMixture; }
        }
        public TempCtrBoardConfig(int instanceId)
        {
            _sysConfig = SysConfig.GetInstance();
            _instanceId = instanceId;
            IP = _sysConfig.TempSvrAddr.GetItemValue(_instanceId);
            Ports = _sysConfig.GetTempSvrPorts();

            _targetTemp = float.Parse(_sysConfig.HightTempValue.Value);
            //_sysConfig.HightTempValue.DetectOnValueChange(OnValueChange);
            NormalTempHight = float.Parse(_sysConfig.NormalTempHight.Value);
            _tempCompensator = float.Parse(_sysConfig.TempReparation.Value);
            // _sysConfig.TempReparation.DetectOnValueChange(OnValueChange);
            OutWorkVoltage = float.Parse(_sysConfig.WorkVoltage.Value);
            VoltageCloseThreshold = float.Parse(_sysConfig.VoltageCloseThreshold.Value);
            _targetSpeed = Int16.Parse(_sysConfig.FanPowerPrecent.Value);
            //_sysConfig.FanPowerPrecent.DetectOnValueChange(OnValueChange);

            _speedLowerLimit = ushort.Parse(_sysConfig.FanLowSpeed.Value);
            //_sysConfig.FanLowSpeed.DetectOnValueChange(OnValueChange);
            _useDiffCompensator = _sysConfig.UseDiffReparation.CheckBoolValue();
            // _sysConfig.UseDiffReparation.DetectOnValueChange(OnValueChange);
            _tempMistake = float.Parse(_sysConfig.TempMistake.Value);
            NormalTempCheck = _sysConfig.NormalTempCheck.CheckBoolValue();
            //_sysConfig.TempMistake.DetectOnValueChange(OnValueChange);
            //_sysConfig.SiteTempReparation.BindOnMemberChange(OnValueChange, _instanceId);
            LoadDutsTempCompensator();
        }

        private void LoadDutsTempCompensator()
        {
            string tempReparations = _sysConfig.SiteTempReparation.GetItemValue(_instanceId);
            string[] arrayList = tempReparations.Split(',');
            int i = 0;
            _dutsTempCompensator = new float[SysConfig.TEAM_GROUP_NUM * SysConfig.PORT_NUM];

            foreach (var v in arrayList)
            {
                float compensator = 0;
                if (float.TryParse(v, out compensator))
                {
                    _dutsTempCompensator[i] = compensator;
                }
                else
                {
                    _dutsTempCompensator[i] = _tempCompensator;
                }

                i++;
                if (i == _dutsTempCompensator.Length)
                {
                    break;
                }
            }
            for (; i < _dutsTempCompensator.Length; i++)
            {
                _dutsTempCompensator[i] = _tempCompensator;
            }
        }

        private void OnValueChange()
        {
            _targetTemp = float.Parse(_sysConfig.HightTempValue.Value);
            _tempCompensator = float.Parse(_sysConfig.TempReparation.Value);
            //_targetSpeed = Int16.Parse(_sysConfig.FanPowerPrecent.Value);
            //_speedLowerLimit = ushort.Parse(_sysConfig.FanLowSpeed.Value);
            _tempMistake = float.Parse(_sysConfig.TempMistake.Value);
            _useDiffCompensator = _sysConfig.UseDiffReparation.CheckBoolValue();
            LoadDutsTempCompensator();
        }

        public void ReloadConfig()
        {
            OnValueChange();
        }
    }
}
