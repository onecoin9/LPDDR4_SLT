using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL
{
    public class BinCodeManager
    {
        private static BinCodeManager _instance;
        private static readonly object _classLock = new object();
        private byte[] _bin1Codes;
        private byte[] _bin2Codes;
        private byte[] _bin3Codes;
        private byte[] _bin4Codes;
        private byte[] _abnormalCodes;// 测试板异常码
        private byte _defaultBin;
        private SysConfig _sysConfig;
        public byte DefaultBin { get { return _defaultBin; } }
        public void GetBinNumber(byte code, ref byte binNumber)
        {
            //if (code == 0) // 代表空闲Dut ，不需要分bin
            //{
            //    binNumber = 0;
            //    return ;
            //}
            if (_bin1Codes.Contains(code))
            {
                binNumber = 1;
                return ;
            }
            else if (_bin2Codes.Contains(code))
            {
                binNumber = 2;
                return ;
            }
            else if (_bin3Codes.Contains(code))
            {
                binNumber = 3;
                return ;
            }
            else if (_bin4Codes.Contains(code))
            {
                binNumber = 4;
                return ;
            }
            binNumber = DefaultBin;
        }

        private void ParseCodes(string strCodes, ref byte[] outCode)
        {
            if (strCodes == null || strCodes.Length == 0)
            {
                outCode = new byte[0];
                return;
            }
            string[] binCodes = strCodes.Split(',');
            byte[] binCode = new byte[binCodes.Length];
            int i = 0;
            NumberStyles style = NumberStyles.HexNumber;
            IFormatProvider provider = CultureInfo.InvariantCulture;
            foreach (string v in binCodes)
            {
                int result = 0;
                if (int.TryParse(v, style, provider, out result))
                {
                    if (result >= byte.MinValue && result <= byte.MaxValue)
                    {
                        binCode[i++] = Convert.ToByte(v, 16);
                    }
                }
            }
            outCode = new byte[i];
            Array.Copy(binCode, outCode, i);
        }
        private void LoadConfig()
        {
            ParseCodes(_sysConfig.CodeToBin.GetItemValue(0), ref _bin1Codes);
            ParseCodes(_sysConfig.CodeToBin.GetItemValue(1), ref _bin2Codes);
            ParseCodes(_sysConfig.CodeToBin.GetItemValue(2), ref _bin3Codes);
            ParseCodes(_sysConfig.CodeToBin.GetItemValue(3), ref _bin4Codes);

            ParseCodes(_sysConfig.TestboardEvCode.Value, ref _abnormalCodes);
            

            if (!byte.TryParse(_sysConfig.DefaultBin.Value, out _defaultBin))
            {
                _defaultBin = 4;
            }
        }

        private BinCodeManager()
        {
            _sysConfig = SysConfig.GetInstance();
            _sysConfig.CodeToBin.BindOnMemberChange(OnBin1CodeSettingChange, 0);
            _sysConfig.CodeToBin.BindOnMemberChange(OnBin2CodeSettingChange, 1);
            _sysConfig.CodeToBin.BindOnMemberChange(OnBin3CodeSettingChange, 2);
            _sysConfig.CodeToBin.BindOnMemberChange(OnBin4CodeSettingChange, 3);
            _sysConfig.DefaultBin.DetectOnValueChange(OnDefaultBinSettingChange);
            LoadConfig();
        }

        private void OnBin1CodeSettingChange()
        {
            ParseCodes(_sysConfig.CodeToBin.GetItemValue(0), ref _bin1Codes);
        }

        private void OnBin2CodeSettingChange()
        {
            ParseCodes(_sysConfig.CodeToBin.GetItemValue(1), ref _bin2Codes);
        }

        private void OnBin3CodeSettingChange()
        {
            ParseCodes(_sysConfig.CodeToBin.GetItemValue(2), ref _bin3Codes);
        }

        private void OnBin4CodeSettingChange()
        {
            ParseCodes(_sysConfig.CodeToBin.GetItemValue(3), ref _bin4Codes);
        }

        private void OnDefaultBinSettingChange()
        {
            if (!byte.TryParse(_sysConfig.DefaultBin.Value, out _defaultBin))
            {
                _defaultBin = 4;
            }
        }
        public static BinCodeManager GetInstance()
        {
            if (_instance == null)
            {
                lock (_classLock)
                {
                    if (_instance == null)
                    {
                        _instance = new BinCodeManager();
                    }
                }
            }
            return _instance;
        }

        /// <summary>
        /// 检查测试板异常的错误码
        /// </summary>
        /// <param name="errorCode"></param>
        /// <returns></returns>
        public bool CheckAbnormalErrorCode(byte errorCode)
        {
            if (_abnormalCodes.Contains(errorCode))
            {
                return true;
            }
            return false;
        }
    }
}
