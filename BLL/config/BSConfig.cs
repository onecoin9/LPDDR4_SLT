using Hsg.Common;
using Hsg.Common.ADO;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.config
{

    public class BSConfig
    {
        private SysConfig _sysConfig;
        private bool _bConfigChange;
        private IOnMembersChange _onConfigChange;
        public const UInt32 ATTR_EMI = 0x01;
        public const UInt32 ATTR_VERSION = 0x02;
        private UInt32 _changeAttr;
        public Int32 TeamReadyTimeout
        {
            get { return Int32.Parse(_sysConfig.TeamWaitReadyTimeout.Value); }
        }
   		public string DetailFixeTitle
        {
            get { return _sysConfig.CSVDetailTitle.Value; }
        }
        public string RecordFixeTitle
        {
            get { return _sysConfig.CSVRecordTitle.Value; }
        }
        public string OverviewTitle
        {
            get { return _sysConfig.OverviewTitle.Value; }
        }

        //private byte[] _bin1Codes;
        //private byte[] _bin2Codes;
        //private byte[] _bin3Codes;
        //private byte[] _bin4Codes;
        //private byte _defaultBin;
        public bool OpenTempMgr
        {
            get { return SysConfig.TempState == (byte)TempState.TmpHight || SysConfig.TempState == (byte)TempState.TmpMixture; }
        }
        public string HightTempValue
        {
            get { return _sysConfig.HightTempValue.Value; }
        }
        private BinCodeManager _binCodeMgr;
        public byte GetBinNumber(byte code)
        {
            //if (code == 0) // 代表空闲Dut ，不需要分bin
            //{
            //    return 0;
            //}
            //if (_bin1Codes.Contains(code))
            //{
            //    return 1;
            //}
            //else if (_bin2Codes.Contains(code))
            //{
            //    return 2;
            //}
            //else if (_bin3Codes.Contains(code))
            //{
            //    return 3;
            //}
            //else if (_bin4Codes.Contains(code))
            //{
            //    return 4;
            //}
            //return _defaultBin;
            byte binCode = code;
            _binCodeMgr.GetBinNumber(code, ref binCode);
            return binCode;
        }

        public int configVersion
        {
            get { return int.Parse(_sysConfig.ConfigVersion.Value); }
        }

        public int DutOrder
        {
            get { return int.Parse(_sysConfig.DutOrder.Value); }
        }

        //private void ParseBinCodes(string strBinCodes, ref byte[] outBinCode)
        //{
        //    if (strBinCodes == null || strBinCodes.Length == 0)
        //    {
        //        outBinCode = new byte[0];
        //        return;
        //    }
        //    string[] binCodes = strBinCodes.Split(',');
        //    byte[] binCode = new byte[binCodes.Length];
        //    int i = 0;
        //    NumberStyles style = NumberStyles.HexNumber;
        //    IFormatProvider provider = CultureInfo.InvariantCulture;
        //    foreach (string v in binCodes)
        //    {
        //        int result = 0;
        //        if (int.TryParse(v, style, provider, out result))
        //        {
        //            if (result >= byte.MinValue && result <= byte.MaxValue)
        //            {
        //                binCode[i++] = Convert.ToByte(v, 16);
        //            }
        //        }
        //    }
        //    outBinCode = new byte[i];
        //    Array.Copy(binCode, outBinCode, i);
        //}
        //private void LoadBinCodes()
        //{
        //    ParseBinCodes(_sysConfig.CodeToBin.GetItemValue(0), ref _bin1Codes);
        //    ParseBinCodes(_sysConfig.CodeToBin.GetItemValue(1), ref _bin2Codes);
        //    ParseBinCodes(_sysConfig.CodeToBin.GetItemValue(2), ref _bin3Codes);
        //    ParseBinCodes(_sysConfig.CodeToBin.GetItemValue(3), ref _bin4Codes);

        //    if (!byte.TryParse(_sysConfig.DefaultBin.Value, out _defaultBin))
        //    {
        //        _defaultBin = 4;
        //    }
        //}
        public BSConfig(IOnMembersChange onConfigChange)
        {
            _sysConfig = SysConfig.GetInstance();
            _sysConfig.DebugPolicyConfig.DetectOnValueChange(OnEmiSettingChange);

            _sysConfig.ConfigVersion.DetectOnValueChange(OnConfigVersionChange);


            _sysConfig.OnConfigUpdate += NotifyConfigUpdate;
            _onConfigChange = onConfigChange;
            _changeAttr = 0;
            _binCodeMgr = BinCodeManager.GetInstance();
            //  LoadBinCodes();
        }
        private void OnEmiSettingChange()
        {
            _bConfigChange = true;
            _changeAttr |= ATTR_EMI;
        }

        private void OnConfigVersionChange()
        {
            _bConfigChange = true;
            _changeAttr |= ATTR_VERSION;
        }



        private void NotifyConfigUpdate()
        {
            if (_onConfigChange != null && _bConfigChange)
            {
                _bConfigChange = false;
                _onConfigChange(_changeAttr);
            }
            _changeAttr = 0;
        }
    }
}
