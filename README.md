# AI Office Việt Nam

Ứng dụng Windows chuyển PDF sang Word, sử dụng Gemini để nhận dạng PDF scan, sửa lỗi chính tả tiếng Việt và khôi phục nội dung bị lỗi font. File Word đầu ra được chuẩn hóa mặc định:

- Font **Times New Roman**
- Cỡ chữ **14**
- Khổ giấy **A4**
- Lề trái 3 cm; phải, trên, dưới 2 cm
- Giãn dòng 1,5

## Chức năng bản 0.1.0

- Kéo thả một hoặc nhiều file PDF.
- Chuyển PDF có chữ hoặc PDF scan sang DOCX.
- Gemini đọc trực tiếp tài liệu PDF theo từng nhóm trang.
- Sửa lỗi chính tả, dấu tiếng Việt và lỗi font dựa trên hình ảnh gốc.
- Giữ tiêu đề, căn giữa/căn phải, danh sách và bảng ở mức tốt nhất.
- Trích xuất hình ảnh, chữ ký và con dấu riêng; bỏ qua ảnh scan toàn trang.
- Tạo nhật ký các lỗi AI đã sửa bên cạnh file Word.
- Chế độ không AI cho PDF có lớp văn bản.
- Xử lý hàng loạt và mở nhanh thư mục kết quả.

## Lưu ý về dữ liệu

Khi bật Gemini, từng nhóm trang PDF được tải tạm thời lên Gemini API để nhận dạng và hiệu đính. Google cho biết tệp tải bằng Files API được lưu tạm thời; ứng dụng cũng chủ động xóa tệp ngay sau khi xử lý. Không đưa tài liệu mật lên dịch vụ AI nếu đơn vị chưa cho phép.

## Cài đặt để chạy mã nguồn

Yêu cầu Windows 10/11 64-bit và Python 3.11 hoặc 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m ai_office_vietnam.main
```

Mở **Cài đặt Gemini**, nhập API key từ Google AI Studio, bấm **Kiểm tra kết nối**, sau đó lưu.

## Tạo file EXE trên Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\build\build_exe.ps1
```

Kết quả:

```text
dist\AI-Office-Viet-Nam.exe
```

## Tự động build trên GitHub

Workflow `.github/workflows/build-windows.yml` chạy kiểm thử và build trên `windows-latest`. Sau mỗi lần đẩy mã lên nhánh `main` hoặc chạy thủ công, tải artifact `AI-Office-Viet-Nam-Windows` trong phần **Actions**.

## Phạm vi bản đầu tiên

Đây là bản MVP sử dụng được. Chất lượng tái tạo bố cục phức tạp phụ thuộc tài liệu và phản hồi Gemini. Các biểu mẫu nhiều cột, sơ đồ, chữ viết tay hoặc bảng phức tạp có thể cần chỉnh lại trong Word.
