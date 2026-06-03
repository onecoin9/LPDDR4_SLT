namespace Hsg.View
{
    partial class PolicyControl
    {
        /// <summary> 
        /// 必需的设计器变量。
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary> 
        /// 清理所有正在使用的资源。
        /// </summary>
        /// <param name="disposing">如果应释放托管资源，为 true；否则为 false。</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region 组件设计器生成的代码

        /// <summary> 
        /// 设计器支持所需的方法 - 不要修改
        /// 使用代码编辑器修改此方法的内容。
        /// </summary>
        private void InitializeComponent()
        {
            this.txt_config_name = new System.Windows.Forms.TextBox();
            this.label1 = new System.Windows.Forms.Label();
            this.btn_select_config = new System.Windows.Forms.Button();
            this.nud_timeoutMin = new System.Windows.Forms.NumericUpDown();
            this.label8 = new System.Windows.Forms.Label();
            this.nud_frequency = new System.Windows.Forms.NumericUpDown();
            this.label2 = new System.Windows.Forms.Label();
            this.txt_description = new System.Windows.Forms.TextBox();
            this.lab_id = new System.Windows.Forms.Label();
            this.label4 = new System.Windows.Forms.Label();
            this.btn_delete = new System.Windows.Forms.Button();
            this.btn_add = new System.Windows.Forms.Button();
            this.nud_allow_fail = new System.Windows.Forms.NumericUpDown();
            this.label3 = new System.Windows.Forms.Label();
            this.label6 = new System.Windows.Forms.Label();
            this.cbx_result_optimization = new System.Windows.Forms.CheckBox();
            this.label5 = new System.Windows.Forms.Label();
            this.rbt_hight_tmp = new System.Windows.Forms.RadioButton();
            this.rbt_normal_tmp = new System.Windows.Forms.RadioButton();
            ((System.ComponentModel.ISupportInitialize)(this.nud_timeoutMin)).BeginInit();
            ((System.ComponentModel.ISupportInitialize)(this.nud_frequency)).BeginInit();
            ((System.ComponentModel.ISupportInitialize)(this.nud_allow_fail)).BeginInit();
            this.SuspendLayout();
            // 
            // txt_config_name
            // 
            this.txt_config_name.Location = new System.Drawing.Point(108, 65);
            this.txt_config_name.Margin = new System.Windows.Forms.Padding(4);
            this.txt_config_name.Name = "txt_config_name";
            this.txt_config_name.ReadOnly = true;
            this.txt_config_name.Size = new System.Drawing.Size(403, 26);
            this.txt_config_name.TabIndex = 0;
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Location = new System.Drawing.Point(9, 70);
            this.label1.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(80, 16);
            this.label1.TabIndex = 1;
            this.label1.Text = "配置文件:";
            // 
            // btn_select_config
            // 
            this.btn_select_config.Location = new System.Drawing.Point(518, 65);
            this.btn_select_config.Name = "btn_select_config";
            this.btn_select_config.Size = new System.Drawing.Size(77, 26);
            this.btn_select_config.TabIndex = 2;
            this.btn_select_config.Text = "选择";
            this.btn_select_config.UseVisualStyleBackColor = true;
            this.btn_select_config.Click += new System.EventHandler(this.OnSelectCfgFileClick);
            // 
            // nud_timeoutMin
            // 
            this.nud_timeoutMin.ImeMode = System.Windows.Forms.ImeMode.NoControl;
            this.nud_timeoutMin.Location = new System.Drawing.Point(108, 99);
            this.nud_timeoutMin.Maximum = new decimal(new int[] {
            10000,
            0,
            0,
            0});
            this.nud_timeoutMin.Name = "nud_timeoutMin";
            this.nud_timeoutMin.Size = new System.Drawing.Size(106, 26);
            this.nud_timeoutMin.TabIndex = 6;
            this.nud_timeoutMin.ThousandsSeparator = true;
            // 
            // label8
            // 
            this.label8.AutoSize = true;
            this.label8.Location = new System.Drawing.Point(9, 104);
            this.label8.Name = "label8";
            this.label8.Size = new System.Drawing.Size(88, 16);
            this.label8.TabIndex = 5;
            this.label8.Text = "测试超时：";
            // 
            // nud_frequency
            // 
            this.nud_frequency.Location = new System.Drawing.Point(108, 140);
            this.nud_frequency.Maximum = new decimal(new int[] {
            1000000,
            0,
            0,
            0});
            this.nud_frequency.Minimum = new decimal(new int[] {
            1,
            0,
            0,
            0});
            this.nud_frequency.Name = "nud_frequency";
            this.nud_frequency.Size = new System.Drawing.Size(67, 26);
            this.nud_frequency.TabIndex = 11;
            this.nud_frequency.Value = new decimal(new int[] {
            1,
            0,
            0,
            0});
            // 
            // label2
            // 
            this.label2.AutoSize = true;
            this.label2.Location = new System.Drawing.Point(9, 36);
            this.label2.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label2.Name = "label2";
            this.label2.Size = new System.Drawing.Size(80, 16);
            this.label2.TabIndex = 1;
            this.label2.Text = "功能描述:";
            // 
            // txt_description
            // 
            this.txt_description.Location = new System.Drawing.Point(108, 31);
            this.txt_description.Margin = new System.Windows.Forms.Padding(4);
            this.txt_description.Name = "txt_description";
            this.txt_description.Size = new System.Drawing.Size(403, 26);
            this.txt_description.TabIndex = 0;
            // 
            // lab_id
            // 
            this.lab_id.AutoSize = true;
            this.lab_id.Location = new System.Drawing.Point(10, 5);
            this.lab_id.Name = "lab_id";
            this.lab_id.Size = new System.Drawing.Size(16, 16);
            this.lab_id.TabIndex = 17;
            this.lab_id.Text = "1";
            // 
            // label4
            // 
            this.label4.AutoSize = true;
            this.label4.Location = new System.Drawing.Point(221, 104);
            this.label4.Name = "label4";
            this.label4.Size = new System.Drawing.Size(24, 16);
            this.label4.TabIndex = 18;
            this.label4.Text = "分";
            // 
            // btn_delete
            // 
            this.btn_delete.Location = new System.Drawing.Point(591, 3);
            this.btn_delete.Name = "btn_delete";
            this.btn_delete.Size = new System.Drawing.Size(75, 30);
            this.btn_delete.TabIndex = 19;
            this.btn_delete.Text = "删除";
            this.btn_delete.UseVisualStyleBackColor = true;
            // 
            // btn_add
            // 
            this.btn_add.Location = new System.Drawing.Point(591, 166);
            this.btn_add.Name = "btn_add";
            this.btn_add.Size = new System.Drawing.Size(75, 30);
            this.btn_add.TabIndex = 19;
            this.btn_add.Text = "添加\r\n";
            this.btn_add.UseVisualStyleBackColor = true;
            // 
            // nud_allow_fail
            // 
            this.nud_allow_fail.Location = new System.Drawing.Point(305, 140);
            this.nud_allow_fail.Maximum = new decimal(new int[] {
            1000000,
            0,
            0,
            0});
            this.nud_allow_fail.Name = "nud_allow_fail";
            this.nud_allow_fail.Size = new System.Drawing.Size(67, 26);
            this.nud_allow_fail.TabIndex = 11;
            // 
            // label3
            // 
            this.label3.AutoSize = true;
            this.label3.Location = new System.Drawing.Point(9, 145);
            this.label3.Name = "label3";
            this.label3.Size = new System.Drawing.Size(80, 16);
            this.label3.TabIndex = 20;
            this.label3.Text = "执行次数:";
            // 
            // label6
            // 
            this.label6.AutoSize = true;
            this.label6.Location = new System.Drawing.Point(214, 145);
            this.label6.Name = "label6";
            this.label6.Size = new System.Drawing.Size(80, 16);
            this.label6.TabIndex = 20;
            this.label6.Text = "允许失败:";
            // 
            // cbx_result_optimization
            // 
            this.cbx_result_optimization.AutoSize = true;
            this.cbx_result_optimization.Location = new System.Drawing.Point(415, 143);
            this.cbx_result_optimization.Name = "cbx_result_optimization";
            this.cbx_result_optimization.Size = new System.Drawing.Size(91, 20);
            this.cbx_result_optimization.TabIndex = 12;
            this.cbx_result_optimization.Text = "结果优化";
            this.cbx_result_optimization.UseVisualStyleBackColor = true;
            // 
            // label5
            // 
            this.label5.AutoSize = true;
            this.label5.BackColor = System.Drawing.SystemColors.Control;
            this.label5.ForeColor = System.Drawing.SystemColors.MenuHighlight;
            this.label5.Location = new System.Drawing.Point(294, 177);
            this.label5.Name = "label5";
            this.label5.Size = new System.Drawing.Size(224, 16);
            this.label5.TabIndex = 21;
            this.label5.Text = "允许失败次数为0代表，不限制";
            // 
            // rbt_hight_tmp
            // 
            this.rbt_hight_tmp.AutoSize = true;
            this.rbt_hight_tmp.Location = new System.Drawing.Point(224, 6);
            this.rbt_hight_tmp.Name = "rbt_hight_tmp";
            this.rbt_hight_tmp.Size = new System.Drawing.Size(58, 20);
            this.rbt_hight_tmp.TabIndex = 22;
            this.rbt_hight_tmp.Text = "高温";
            this.rbt_hight_tmp.UseVisualStyleBackColor = true;
            // 
            // rbt_normal_tmp
            // 
            this.rbt_normal_tmp.AutoSize = true;
            this.rbt_normal_tmp.Checked = true;
            this.rbt_normal_tmp.Location = new System.Drawing.Point(108, 6);
            this.rbt_normal_tmp.Name = "rbt_normal_tmp";
            this.rbt_normal_tmp.Size = new System.Drawing.Size(58, 20);
            this.rbt_normal_tmp.TabIndex = 23;
            this.rbt_normal_tmp.TabStop = true;
            this.rbt_normal_tmp.Text = "常温";
            this.rbt_normal_tmp.UseVisualStyleBackColor = true;
            // 
            // PolicyControl
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(8F, 16F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.BorderStyle = System.Windows.Forms.BorderStyle.Fixed3D;
            this.Controls.Add(this.rbt_normal_tmp);
            this.Controls.Add(this.rbt_hight_tmp);
            this.Controls.Add(this.label5);
            this.Controls.Add(this.label6);
            this.Controls.Add(this.label3);
            this.Controls.Add(this.btn_add);
            this.Controls.Add(this.btn_delete);
            this.Controls.Add(this.label4);
            this.Controls.Add(this.lab_id);
            this.Controls.Add(this.cbx_result_optimization);
            this.Controls.Add(this.nud_allow_fail);
            this.Controls.Add(this.nud_frequency);
            this.Controls.Add(this.nud_timeoutMin);
            this.Controls.Add(this.label8);
            this.Controls.Add(this.btn_select_config);
            this.Controls.Add(this.label2);
            this.Controls.Add(this.label1);
            this.Controls.Add(this.txt_description);
            this.Controls.Add(this.txt_config_name);
            this.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.Margin = new System.Windows.Forms.Padding(4);
            this.Name = "PolicyControl";
            this.Size = new System.Drawing.Size(670, 199);
            ((System.ComponentModel.ISupportInitialize)(this.nud_timeoutMin)).EndInit();
            ((System.ComponentModel.ISupportInitialize)(this.nud_frequency)).EndInit();
            ((System.ComponentModel.ISupportInitialize)(this.nud_allow_fail)).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.TextBox txt_config_name;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.Button btn_select_config;
        private System.Windows.Forms.NumericUpDown nud_timeoutMin;
        private System.Windows.Forms.Label label8;
        private System.Windows.Forms.NumericUpDown nud_frequency;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.TextBox txt_description;
        private System.Windows.Forms.Label lab_id;
        private System.Windows.Forms.Label label4;
        private System.Windows.Forms.Button btn_delete;
        private System.Windows.Forms.Button btn_add;
        private System.Windows.Forms.NumericUpDown nud_allow_fail;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.Label label6;
        private System.Windows.Forms.CheckBox cbx_result_optimization;
        private System.Windows.Forms.Label label5;
        private System.Windows.Forms.RadioButton rbt_hight_tmp;
        private System.Windows.Forms.RadioButton rbt_normal_tmp;
    }
}
