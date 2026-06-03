namespace Hsg.View
{
    partial class SettingForm
    {
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            this.groupBox2 = new System.Windows.Forms.GroupBox();
            this.groupBox5 = new System.Windows.Forms.GroupBox();
            this.m_ckb_save_log = new System.Windows.Forms.CheckBox();
            this.m_btn_csv_setting = new System.Windows.Forms.Button();
            this.m_btn_log_setting = new System.Windows.Forms.Button();
            this.groupBox4 = new System.Windows.Forms.GroupBox();
            this.m_rbt_ui_style2 = new System.Windows.Forms.RadioButton();
            this.m_rbt_ui_style1 = new System.Windows.Forms.RadioButton();
            this.groupBox3 = new System.Windows.Forms.GroupBox();
            this.m_cbx_selected_io = new System.Windows.Forms.ComboBox();
            this.m_nud_Io_start = new System.Windows.Forms.NumericUpDown();
            this.m_nud_io_span = new System.Windows.Forms.NumericUpDown();
            this.label4 = new System.Windows.Forms.Label();
            this.label3 = new System.Windows.Forms.Label();
            this.m_btn_select_emi = new System.Windows.Forms.Button();
            this.m_txt_config_path = new System.Windows.Forms.TextBox();
            this.label7 = new System.Windows.Forms.Label();
            this.label5 = new System.Windows.Forms.Label();
            this.m_btn_ok = new System.Windows.Forms.Button();
            this.m_btn_cancel = new System.Windows.Forms.Button();
            this.label1 = new System.Windows.Forms.Label();
            this.label6 = new System.Windows.Forms.Label();
            this.label2 = new System.Windows.Forms.Label();
            this.m_nud_timeout = new System.Windows.Forms.NumericUpDown();
            this.m_nud_dest_port = new System.Windows.Forms.NumericUpDown();
            this.m_txt_dest_ip = new System.Windows.Forms.TextBox();
            this.groupBox1 = new System.Windows.Forms.GroupBox();
            this.m_pal_ip_list = new System.Windows.Forms.Panel();
            this.m_gbx_ip_list = new System.Windows.Forms.GroupBox();
            this.groupBox6 = new System.Windows.Forms.GroupBox();
            this.m_rbt_groupB = new System.Windows.Forms.RadioButton();
            this.m_rbt_groupA = new System.Windows.Forms.RadioButton();
            this.groupBox7 = new System.Windows.Forms.GroupBox();
            this.m_rbt_order02 = new System.Windows.Forms.RadioButton();
            this.m_rbt_order01 = new System.Windows.Forms.RadioButton();
            this.groupBox8 = new System.Windows.Forms.GroupBox();
            this.m_cbx_board_protocol = new System.Windows.Forms.ComboBox();
            this.button2 = new System.Windows.Forms.Button();
            this.groupBox2.SuspendLayout();
            this.groupBox5.SuspendLayout();
            this.groupBox4.SuspendLayout();
            this.groupBox3.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.m_nud_Io_start)).BeginInit();
            ((System.ComponentModel.ISupportInitialize)(this.m_nud_io_span)).BeginInit();
            ((System.ComponentModel.ISupportInitialize)(this.m_nud_timeout)).BeginInit();
            ((System.ComponentModel.ISupportInitialize)(this.m_nud_dest_port)).BeginInit();
            this.groupBox1.SuspendLayout();
            this.m_gbx_ip_list.SuspendLayout();
            this.groupBox6.SuspendLayout();
            this.groupBox7.SuspendLayout();
            this.groupBox8.SuspendLayout();
            this.SuspendLayout();
            // 
            // groupBox2
            // 
            this.groupBox2.Controls.Add(this.groupBox5);
            this.groupBox2.Controls.Add(this.groupBox4);
            this.groupBox2.Controls.Add(this.groupBox3);
            this.groupBox2.Controls.Add(this.m_btn_select_emi);
            this.groupBox2.Controls.Add(this.m_txt_config_path);
            this.groupBox2.Controls.Add(this.label7);
            this.groupBox2.Location = new System.Drawing.Point(7, 97);
            this.groupBox2.Name = "groupBox2";
            this.groupBox2.Size = new System.Drawing.Size(1029, 195);
            this.groupBox2.TabIndex = 1;
            this.groupBox2.TabStop = false;
            this.groupBox2.Text = "测试参数控制";
            // 
            // groupBox5
            // 
            this.groupBox5.Controls.Add(this.m_ckb_save_log);
            this.groupBox5.Controls.Add(this.m_btn_csv_setting);
            this.groupBox5.Controls.Add(this.m_btn_log_setting);
            this.groupBox5.Location = new System.Drawing.Point(718, 88);
            this.groupBox5.Name = "groupBox5";
            this.groupBox5.Size = new System.Drawing.Size(295, 101);
            this.groupBox5.TabIndex = 4;
            this.groupBox5.TabStop = false;
            this.groupBox5.Text = "其他设置";
            // 
            // m_ckb_save_log
            // 
            this.m_ckb_save_log.AutoSize = true;
            this.m_ckb_save_log.Location = new System.Drawing.Point(9, 29);
            this.m_ckb_save_log.Name = "m_ckb_save_log";
            this.m_ckb_save_log.Size = new System.Drawing.Size(182, 28);
            this.m_ckb_save_log.TabIndex = 0;
            this.m_ckb_save_log.Text = "接收测试日志";
            this.m_ckb_save_log.UseVisualStyleBackColor = true;
            // 
            // m_btn_csv_setting
            // 
            this.m_btn_csv_setting.Font = new System.Drawing.Font("新宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_btn_csv_setting.Location = new System.Drawing.Point(169, 58);
            this.m_btn_csv_setting.Name = "m_btn_csv_setting";
            this.m_btn_csv_setting.Size = new System.Drawing.Size(119, 33);
            this.m_btn_csv_setting.TabIndex = 3;
            this.m_btn_csv_setting.Text = "CSV设置";
            this.m_btn_csv_setting.UseVisualStyleBackColor = true;
            this.m_btn_csv_setting.Click += new System.EventHandler(this.OnBtnCSVSettingClick);
            // 
            // m_btn_log_setting
            // 
            this.m_btn_log_setting.Font = new System.Drawing.Font("新宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_btn_log_setting.Location = new System.Drawing.Point(10, 58);
            this.m_btn_log_setting.Name = "m_btn_log_setting";
            this.m_btn_log_setting.Size = new System.Drawing.Size(113, 37);
            this.m_btn_log_setting.TabIndex = 3;
            this.m_btn_log_setting.Text = "测试log设置";
            this.m_btn_log_setting.UseVisualStyleBackColor = true;
            this.m_btn_log_setting.Click += new System.EventHandler(this.OnBtnLogSettingClick);
            // 
            // groupBox4
            // 
            this.groupBox4.Controls.Add(this.m_rbt_ui_style2);
            this.groupBox4.Controls.Add(this.m_rbt_ui_style1);
            this.groupBox4.Location = new System.Drawing.Point(547, 88);
            this.groupBox4.Name = "groupBox4";
            this.groupBox4.Size = new System.Drawing.Size(155, 101);
            this.groupBox4.TabIndex = 4;
            this.groupBox4.TabStop = false;
            this.groupBox4.Text = "UI 风格";
            // 
            // m_rbt_ui_style2
            // 
            this.m_rbt_ui_style2.AutoSize = true;
            this.m_rbt_ui_style2.Location = new System.Drawing.Point(6, 60);
            this.m_rbt_ui_style2.Name = "m_rbt_ui_style2";
            this.m_rbt_ui_style2.Size = new System.Drawing.Size(107, 28);
            this.m_rbt_ui_style2.TabIndex = 0;
            this.m_rbt_ui_style2.TabStop = true;
            this.m_rbt_ui_style2.Text = "4列8行";
            this.m_rbt_ui_style2.UseVisualStyleBackColor = true;
            // 
            // m_rbt_ui_style1
            // 
            this.m_rbt_ui_style1.AutoSize = true;
            this.m_rbt_ui_style1.Location = new System.Drawing.Point(6, 29);
            this.m_rbt_ui_style1.Name = "m_rbt_ui_style1";
            this.m_rbt_ui_style1.Size = new System.Drawing.Size(171, 28);
            this.m_rbt_ui_style1.TabIndex = 0;
            this.m_rbt_ui_style1.TabStop = true;
            this.m_rbt_ui_style1.Text = "3列10、11行";
            this.m_rbt_ui_style1.UseVisualStyleBackColor = true;
            // 
            // groupBox3
            // 
            this.groupBox3.Controls.Add(this.m_cbx_selected_io);
            this.groupBox3.Controls.Add(this.m_nud_Io_start);
            this.groupBox3.Controls.Add(this.m_nud_io_span);
            this.groupBox3.Controls.Add(this.label4);
            this.groupBox3.Controls.Add(this.label3);
            this.groupBox3.Location = new System.Drawing.Point(7, 80);
            this.groupBox3.Name = "groupBox3";
            this.groupBox3.Size = new System.Drawing.Size(516, 109);
            this.groupBox3.TabIndex = 0;
            this.groupBox3.TabStop = false;
            this.groupBox3.Text = "延迟IO控制";
            // 
            // m_cbx_selected_io
            // 
            this.m_cbx_selected_io.DisplayMember = "fab c d";
            this.m_cbx_selected_io.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.m_cbx_selected_io.FormattingEnabled = true;
            this.m_cbx_selected_io.Location = new System.Drawing.Point(112, 20);
            this.m_cbx_selected_io.Name = "m_cbx_selected_io";
            this.m_cbx_selected_io.Size = new System.Drawing.Size(369, 32);
            this.m_cbx_selected_io.TabIndex = 6;
            this.m_cbx_selected_io.SelectedIndexChanged += new System.EventHandler(this.OnSelectIOChange);
            // 
            // m_nud_Io_start
            // 
            this.m_nud_Io_start.Location = new System.Drawing.Point(152, 69);
            this.m_nud_Io_start.Maximum = new decimal(new int[] {
            1000,
            0,
            0,
            0});
            this.m_nud_Io_start.Name = "m_nud_Io_start";
            this.m_nud_Io_start.ReadOnly = true;
            this.m_nud_Io_start.Size = new System.Drawing.Size(90, 35);
            this.m_nud_Io_start.TabIndex = 7;
            this.m_nud_Io_start.Value = new decimal(new int[] {
            1,
            0,
            0,
            0});
            // 
            // m_nud_io_span
            // 
            this.m_nud_io_span.Location = new System.Drawing.Point(391, 69);
            this.m_nud_io_span.Maximum = new decimal(new int[] {
            1000,
            0,
            0,
            0});
            this.m_nud_io_span.Minimum = new decimal(new int[] {
            1,
            0,
            0,
            0});
            this.m_nud_io_span.Name = "m_nud_io_span";
            this.m_nud_io_span.ReadOnly = true;
            this.m_nud_io_span.Size = new System.Drawing.Size(90, 35);
            this.m_nud_io_span.TabIndex = 8;
            this.m_nud_io_span.Value = new decimal(new int[] {
            1,
            0,
            0,
            0});
            // 
            // label4
            // 
            this.label4.AutoSize = true;
            this.label4.Location = new System.Drawing.Point(248, 74);
            this.label4.Name = "label4";
            this.label4.Size = new System.Drawing.Size(162, 24);
            this.label4.TabIndex = 4;
            this.label4.Text = "持续时间(s):";
            // 
            // label3
            // 
            this.label3.AutoSize = true;
            this.label3.Location = new System.Drawing.Point(6, 74);
            this.label3.Name = "label3";
            this.label3.Size = new System.Drawing.Size(162, 24);
            this.label3.TabIndex = 5;
            this.label3.Text = "启动时间(s):";
            // 
            // m_btn_select_emi
            // 
            this.m_btn_select_emi.Location = new System.Drawing.Point(918, 26);
            this.m_btn_select_emi.Name = "m_btn_select_emi";
            this.m_btn_select_emi.Size = new System.Drawing.Size(105, 36);
            this.m_btn_select_emi.TabIndex = 3;
            this.m_btn_select_emi.Text = "选择EMI";
            this.m_btn_select_emi.UseVisualStyleBackColor = true;
            this.m_btn_select_emi.Click += new System.EventHandler(this.OnBtnSelectEmiClick);
            // 
            // m_txt_config_path
            // 
            this.m_txt_config_path.Anchor = ((System.Windows.Forms.AnchorStyles)(((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.m_txt_config_path.Location = new System.Drawing.Point(198, 27);
            this.m_txt_config_path.Name = "m_txt_config_path";
            this.m_txt_config_path.RightToLeft = System.Windows.Forms.RightToLeft.Yes;
            this.m_txt_config_path.Size = new System.Drawing.Size(717, 35);
            this.m_txt_config_path.TabIndex = 2;
            this.m_txt_config_path.TextAlign = System.Windows.Forms.HorizontalAlignment.Right;
            // 
            // label7
            // 
            this.label7.AutoSize = true;
            this.label7.Location = new System.Drawing.Point(6, 31);
            this.label7.Name = "label7";
            this.label7.Size = new System.Drawing.Size(173, 24);
            this.label7.TabIndex = 0;
            this.label7.Text = "测试配置文件:";
            // 
            // label5
            // 
            this.label5.AutoSize = true;
            this.label5.ForeColor = System.Drawing.Color.Red;
            this.label5.Location = new System.Drawing.Point(188, 299);
            this.label5.Name = "label5";
            this.label5.Size = new System.Drawing.Size(627, 24);
            this.label5.TabIndex = 5;
            this.label5.Text = "修改UI 、log、 工作组、 测试板顺序 将自动重启程序";
            // 
            // m_btn_ok
            // 
            this.m_btn_ok.Location = new System.Drawing.Point(237, 699);
            this.m_btn_ok.Name = "m_btn_ok";
            this.m_btn_ok.Size = new System.Drawing.Size(119, 47);
            this.m_btn_ok.TabIndex = 3;
            this.m_btn_ok.Text = "确定";
            this.m_btn_ok.UseVisualStyleBackColor = true;
            this.m_btn_ok.Click += new System.EventHandler(this.OnBtnOKClick);
            // 
            // m_btn_cancel
            // 
            this.m_btn_cancel.Location = new System.Drawing.Point(543, 699);
            this.m_btn_cancel.Name = "m_btn_cancel";
            this.m_btn_cancel.Size = new System.Drawing.Size(119, 47);
            this.m_btn_cancel.TabIndex = 3;
            this.m_btn_cancel.Text = "取消";
            this.m_btn_cancel.UseVisualStyleBackColor = true;
            this.m_btn_cancel.Click += new System.EventHandler(this.OnBtnCancelClick);
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Location = new System.Drawing.Point(3, 35);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(99, 24);
            this.label1.TabIndex = 0;
            this.label1.Text = "机台IP:";
            // 
            // label6
            // 
            this.label6.AutoSize = true;
            this.label6.Location = new System.Drawing.Point(687, 28);
            this.label6.Name = "label6";
            this.label6.Size = new System.Drawing.Size(198, 24);
            this.label6.TabIndex = 0;
            this.label6.Text = "测试超时（分）:";
            // 
            // label2
            // 
            this.label2.AutoSize = true;
            this.label2.Location = new System.Drawing.Point(348, 30);
            this.label2.Name = "label2";
            this.label2.Size = new System.Drawing.Size(174, 24);
            this.label2.TabIndex = 0;
            this.label2.Text = "机台tcp端口：";
            // 
            // m_nud_timeout
            // 
            this.m_nud_timeout.Location = new System.Drawing.Point(859, 23);
            this.m_nud_timeout.Maximum = new decimal(new int[] {
            10000,
            0,
            0,
            0});
            this.m_nud_timeout.Minimum = new decimal(new int[] {
            1,
            0,
            0,
            0});
            this.m_nud_timeout.Name = "m_nud_timeout";
            this.m_nud_timeout.Size = new System.Drawing.Size(120, 35);
            this.m_nud_timeout.TabIndex = 1;
            this.m_nud_timeout.Value = new decimal(new int[] {
            1,
            0,
            0,
            0});
            // 
            // m_nud_dest_port
            // 
            this.m_nud_dest_port.Location = new System.Drawing.Point(496, 25);
            this.m_nud_dest_port.Maximum = new decimal(new int[] {
            65535,
            0,
            0,
            0});
            this.m_nud_dest_port.Minimum = new decimal(new int[] {
            1,
            0,
            0,
            0});
            this.m_nud_dest_port.Name = "m_nud_dest_port";
            this.m_nud_dest_port.Size = new System.Drawing.Size(157, 35);
            this.m_nud_dest_port.TabIndex = 1;
            this.m_nud_dest_port.Value = new decimal(new int[] {
            1,
            0,
            0,
            0});
            // 
            // m_txt_dest_ip
            // 
            this.m_txt_dest_ip.Location = new System.Drawing.Point(123, 28);
            this.m_txt_dest_ip.Name = "m_txt_dest_ip";
            this.m_txt_dest_ip.Size = new System.Drawing.Size(185, 35);
            this.m_txt_dest_ip.TabIndex = 2;
            // 
            // groupBox1
            // 
            this.groupBox1.Controls.Add(this.m_txt_dest_ip);
            this.groupBox1.Controls.Add(this.m_nud_dest_port);
            this.groupBox1.Controls.Add(this.m_nud_timeout);
            this.groupBox1.Controls.Add(this.label2);
            this.groupBox1.Controls.Add(this.label6);
            this.groupBox1.Controls.Add(this.label1);
            this.groupBox1.Location = new System.Drawing.Point(7, 3);
            this.groupBox1.Name = "groupBox1";
            this.groupBox1.Size = new System.Drawing.Size(1032, 76);
            this.groupBox1.TabIndex = 0;
            this.groupBox1.TabStop = false;
            this.groupBox1.Text = "机台参数";
            // 
            // m_pal_ip_list
            // 
            this.m_pal_ip_list.AutoScroll = true;
            this.m_pal_ip_list.Location = new System.Drawing.Point(3, 25);
            this.m_pal_ip_list.Name = "m_pal_ip_list";
            this.m_pal_ip_list.Size = new System.Drawing.Size(780, 299);
            this.m_pal_ip_list.TabIndex = 0;
            // 
            // m_gbx_ip_list
            // 
            this.m_gbx_ip_list.Anchor = ((System.Windows.Forms.AnchorStyles)(((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.m_gbx_ip_list.AutoSize = true;
            this.m_gbx_ip_list.Controls.Add(this.m_pal_ip_list);
            this.m_gbx_ip_list.ImeMode = System.Windows.Forms.ImeMode.Disable;
            this.m_gbx_ip_list.Location = new System.Drawing.Point(7, 319);
            this.m_gbx_ip_list.Name = "m_gbx_ip_list";
            this.m_gbx_ip_list.Size = new System.Drawing.Size(798, 358);
            this.m_gbx_ip_list.TabIndex = 2;
            this.m_gbx_ip_list.TabStop = false;
            this.m_gbx_ip_list.Text = "板卡IP设置";
            // 
            // groupBox6
            // 
            this.groupBox6.Controls.Add(this.m_rbt_groupB);
            this.groupBox6.Controls.Add(this.m_rbt_groupA);
            this.groupBox6.Location = new System.Drawing.Point(811, 319);
            this.groupBox6.Name = "groupBox6";
            this.groupBox6.Size = new System.Drawing.Size(219, 123);
            this.groupBox6.TabIndex = 5;
            this.groupBox6.TabStop = false;
            this.groupBox6.Text = "当前工作组";
            // 
            // m_rbt_groupB
            // 
            this.m_rbt_groupB.AutoSize = true;
            this.m_rbt_groupB.Location = new System.Drawing.Point(29, 90);
            this.m_rbt_groupB.Name = "m_rbt_groupB";
            this.m_rbt_groupB.Size = new System.Drawing.Size(82, 28);
            this.m_rbt_groupB.TabIndex = 0;
            this.m_rbt_groupB.TabStop = true;
            this.m_rbt_groupB.Text = "B 组";
            this.m_rbt_groupB.UseVisualStyleBackColor = true;
            // 
            // m_rbt_groupA
            // 
            this.m_rbt_groupA.AutoSize = true;
            this.m_rbt_groupA.Location = new System.Drawing.Point(29, 50);
            this.m_rbt_groupA.Name = "m_rbt_groupA";
            this.m_rbt_groupA.Size = new System.Drawing.Size(82, 28);
            this.m_rbt_groupA.TabIndex = 0;
            this.m_rbt_groupA.TabStop = true;
            this.m_rbt_groupA.Text = "A 组";
            this.m_rbt_groupA.UseVisualStyleBackColor = true;
            // 
            // groupBox7
            // 
            this.groupBox7.Controls.Add(this.m_rbt_order02);
            this.groupBox7.Controls.Add(this.m_rbt_order01);
            this.groupBox7.Location = new System.Drawing.Point(811, 448);
            this.groupBox7.Name = "groupBox7";
            this.groupBox7.Size = new System.Drawing.Size(219, 125);
            this.groupBox7.TabIndex = 5;
            this.groupBox7.TabStop = false;
            this.groupBox7.Text = "测试板编号顺序";
            // 
            // m_rbt_order02
            // 
            this.m_rbt_order02.AutoSize = true;
            this.m_rbt_order02.Location = new System.Drawing.Point(29, 90);
            this.m_rbt_order02.Name = "m_rbt_order02";
            this.m_rbt_order02.Size = new System.Drawing.Size(131, 28);
            this.m_rbt_order02.TabIndex = 0;
            this.m_rbt_order02.TabStop = true;
            this.m_rbt_order02.Text = "从右到左";
            this.m_rbt_order02.UseVisualStyleBackColor = true;
            // 
            // m_rbt_order01
            // 
            this.m_rbt_order01.AutoSize = true;
            this.m_rbt_order01.Location = new System.Drawing.Point(29, 50);
            this.m_rbt_order01.Name = "m_rbt_order01";
            this.m_rbt_order01.Size = new System.Drawing.Size(131, 28);
            this.m_rbt_order01.TabIndex = 0;
            this.m_rbt_order01.TabStop = true;
            this.m_rbt_order01.Text = "从左到右";
            this.m_rbt_order01.UseVisualStyleBackColor = true;
            // 
            // groupBox8
            // 
            this.groupBox8.Controls.Add(this.m_cbx_board_protocol);
            this.groupBox8.Location = new System.Drawing.Point(811, 579);
            this.groupBox8.Name = "groupBox8";
            this.groupBox8.Size = new System.Drawing.Size(219, 75);
            this.groupBox8.TabIndex = 5;
            this.groupBox8.TabStop = false;
            this.groupBox8.Text = "通讯板协议";
            // 
            // m_cbx_board_protocol
            // 
            this.m_cbx_board_protocol.DisplayMember = "fab c d";
            this.m_cbx_board_protocol.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.m_cbx_board_protocol.Enabled = false;
            this.m_cbx_board_protocol.FormattingEnabled = true;
            this.m_cbx_board_protocol.Location = new System.Drawing.Point(8, 33);
            this.m_cbx_board_protocol.Name = "m_cbx_board_protocol";
            this.m_cbx_board_protocol.Size = new System.Drawing.Size(202, 32);
            this.m_cbx_board_protocol.TabIndex = 6;
            this.m_cbx_board_protocol.SelectedIndexChanged += new System.EventHandler(this.OnSelectIOChange);
            // 
            // button2
            // 
            this.button2.Location = new System.Drawing.Point(819, 660);
            this.button2.Name = "button2";
            this.button2.Size = new System.Drawing.Size(202, 47);
            this.button2.TabIndex = 3;
            this.button2.Text = "管理员权限";
            this.button2.UseVisualStyleBackColor = true;
            this.button2.Click += new System.EventHandler(this.OnBtnAuthClick);
            // 
            // SettingForm
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(13F, 24F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(1049, 758);
            this.Controls.Add(this.groupBox7);
            this.Controls.Add(this.groupBox8);
            this.Controls.Add(this.groupBox6);
            this.Controls.Add(this.label5);
            this.Controls.Add(this.m_btn_cancel);
            this.Controls.Add(this.button2);
            this.Controls.Add(this.m_btn_ok);
            this.Controls.Add(this.m_gbx_ip_list);
            this.Controls.Add(this.groupBox2);
            this.Controls.Add(this.groupBox1);
            this.Font = new System.Drawing.Font("新宋体", 14.25F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.ImeMode = System.Windows.Forms.ImeMode.Disable;
            this.Margin = new System.Windows.Forms.Padding(6, 5, 6, 5);
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "SettingForm";
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterParent;
            this.Text = "设置";
            this.Load += new System.EventHandler(this.SettingForm_Load);
            this.groupBox2.ResumeLayout(false);
            this.groupBox2.PerformLayout();
            this.groupBox5.ResumeLayout(false);
            this.groupBox5.PerformLayout();
            this.groupBox4.ResumeLayout(false);
            this.groupBox4.PerformLayout();
            this.groupBox3.ResumeLayout(false);
            this.groupBox3.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.m_nud_Io_start)).EndInit();
            ((System.ComponentModel.ISupportInitialize)(this.m_nud_io_span)).EndInit();
            ((System.ComponentModel.ISupportInitialize)(this.m_nud_timeout)).EndInit();
            ((System.ComponentModel.ISupportInitialize)(this.m_nud_dest_port)).EndInit();
            this.groupBox1.ResumeLayout(false);
            this.groupBox1.PerformLayout();
            this.m_gbx_ip_list.ResumeLayout(false);
            this.groupBox6.ResumeLayout(false);
            this.groupBox6.PerformLayout();
            this.groupBox7.ResumeLayout(false);
            this.groupBox7.PerformLayout();
            this.groupBox8.ResumeLayout(false);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion
        private System.Windows.Forms.GroupBox groupBox2;
        private System.Windows.Forms.Button m_btn_select_emi;
        private System.Windows.Forms.TextBox m_txt_config_path;
        private System.Windows.Forms.Label label7;
        private System.Windows.Forms.Button m_btn_ok;
        private System.Windows.Forms.Button m_btn_cancel;
        private System.Windows.Forms.GroupBox groupBox3;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.Label label6;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.NumericUpDown m_nud_timeout;
        private System.Windows.Forms.NumericUpDown m_nud_dest_port;
        private System.Windows.Forms.TextBox m_txt_dest_ip;
        private System.Windows.Forms.GroupBox groupBox1;
        private System.Windows.Forms.ComboBox m_cbx_selected_io;
        private System.Windows.Forms.NumericUpDown m_nud_Io_start;
        private System.Windows.Forms.NumericUpDown m_nud_io_span;
        private System.Windows.Forms.Label label4;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.Label label5;
        private System.Windows.Forms.GroupBox groupBox4;
        private System.Windows.Forms.RadioButton m_rbt_ui_style2;
        private System.Windows.Forms.RadioButton m_rbt_ui_style1;
        private System.Windows.Forms.Panel m_pal_ip_list;
        private System.Windows.Forms.GroupBox m_gbx_ip_list;
        private System.Windows.Forms.GroupBox groupBox5;
        private System.Windows.Forms.CheckBox m_ckb_save_log;
        private System.Windows.Forms.GroupBox groupBox6;
        private System.Windows.Forms.RadioButton m_rbt_groupB;
        private System.Windows.Forms.RadioButton m_rbt_groupA;
        private System.Windows.Forms.GroupBox groupBox7;
        private System.Windows.Forms.RadioButton m_rbt_order02;
        private System.Windows.Forms.RadioButton m_rbt_order01;
        private System.Windows.Forms.Button m_btn_log_setting;
        private System.Windows.Forms.Button m_btn_csv_setting;
        private System.Windows.Forms.GroupBox groupBox8;
        private System.Windows.Forms.ComboBox m_cbx_board_protocol;
        private System.Windows.Forms.Button button2;
    }
}