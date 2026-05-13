# Quy tắt code cho dự án

# flow của dự án
- Dự án phải được code theo flow: lên plan => code => test và fixbug => viết doc, cập nhật readme, viết logs, cập nhật file .sh.
- Trước khi code phải đọc hết các docs và readme để biết tổng quan dựa án.
- Đây là link cho logo, ảnh cá nhân: https://github.com/ambrouse/img, trong repo đó chứa rất nhiều ảnh logo cá nhân bạn cứ lựa dùng thoải mái nhưng phải trong repo đó.
- Dự án phải có venv môi trường riêng, có gitignore, có file .sh để chạy dự án lên trong 1 lệnh.
- Khi code tuyệt đối không được phép tự ý fallback lung tung phải đảm bảo chạy đúng 100% theo yêu cầu, plan, logic mà tôi đề ra.

# Quy tắt lên plan
- Plan phải được viết chi tiết và có các phase cụ thể.
- Cứ code xong một phase phải test lại và đánh giá hiệu năng theo chuẩn production chỉ khi pass test 100% mới qua phase tiếp theo.
- Sau mỗi phase phải đọc lại plan và cập nhật nếu có thay đổi.
- Mỗi phase hay mục điều phải có mục tiêu rõ ràng để đánh giá từng hàm từng thuật toán, kiến trúc theo chuẩn production để đánh giá.

# Quy tắt code
- Phải code trên kiến trúc, thuật toán rõ ràng không code bừa, phải đảm bảo có thể mở rộng và chuẩn product redy ở mức cao.

# Quy tắt test và fixbug
- Khi test phải test runtimne thực tế chứ không phải chỉ chạy file lên không lỗi là được.
- Nếu lỗi phải sửa lỗi theo chuẩn production tránh giảm hiệu năng và không được phá pipeline chính hay sửa cực đoan.
- Phải có các tiêu chuẩn để pass khi test và fix theo plan
- phải test và fix đến khi pass chuẩn 100%.

# Quy tắt viết doc
- Phải viết vào folder ./docs
- Phải tách doc hợp lý không dồn hết vào một file, viết doc rõ ràng chi tiết cho từng vấn đề.

# Quy tắt code frontend
- Phải cập nhật các phong cách thiết kế mới nhất hiện tại từ các web uy tín.
- Phong cách thiết kế hiện đại, tech AI, màu tối làm chủ đạo.
- Có loadscene cho các trang chính load bar ngang như các game.
- Luôn có các animation khi hover, khi nhấn, khi load, animation hiện đại tinh tế không nhàm chán và quê mùa.
- Nếu có podup hay dropdown container thì các podup đó khi xuất hiện phải có animation hiện ra như một gợn nước chứ không đơn giản là opacity hay chỉnh left right, display.
- Thiết kế chuẩn và phù hợp cho từng loại máy từ pc đến lap, mobile, ipad, tv, mỗi loại phải có thiết kế riêng và phù hợp nhất chứ không phải chỉ responesive cơ bản, phải có chuẩn pc, chuẩn mobile, ... cho production
- Bố cục phải tránh chồng chéo văn bản trên máy tính để bàn và thiết bị di động.
- Các brouse web mobile còn có thanh search nên phải tính toán cho trường hợp đó.
- Các loadscene phải là % thật của các process, service thật chứ không phải % ảo cho có.
- Trên loadscene nên ghi cụ thể làm gì tới đâu, được bao nhiêu file rồi

# Quy tắt code backend
- Luôn có liến trúc microservice chuẩn chỉ.
- Chuẩn production lớn tải được tối đa hàng nghìn/ trăm nghìn/ trăm triệu request.
- Có các lớp bảo mật chống hack hay ddox, ....
- Thiết kế và chọn lựa database phù hợp
- Ưu tiên dùng docker cho database.
- Cây thư mục chuẩn product
- Phải code chuẩn production redy từ login  - cơ chế hàng đợi cho service nặng, cấu hình chuẩn chỉ cache reddis, rabbitMQ các service nặng, ....

# Quy tắt github
- Phải setup đầy đủ gitignore chuẩn cho dự án.

# Quy tắt cho file setup.sh
- Dự án luôn có file setup.sh để chạy dựa án với 1 lệnh.
- Mỗi khi cập nhật phải check file setup.sh để cập nhật cho đúng pipeline hiện tại.
- File setup phải có đầy đủ để có thể chạy trên 1 máy hoàn toàn mới từ kiểm tra python, chạy trên linux, chạy trên windown, tạo venv, cài thư viện, setup 100% cho dự án dù trên máy chưa có gì. 

# Quy tắt viết readme
- Phải thiết kế và viết readme chuẩn các github chuyên nghiệp
- Có đầy đủ thông tin từ cách chạy tới phiên bản, demo, các thiết kế logo và License đầy đủ.
- phải chèn các link framework như ví dụ sau:
<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Next.js-14+-000000?style=flat-square&logo=next.js" alt="Next.js" />
</p> 
- Toàn bộ tư duy thiết kế README:
Xác định README là trang bán ý tưởng, không phải docs kỹ thuật.
5 giây đầu phải trả lời: “Project này là gì và đáng thử không?”
Hero phải có 3 lớp: logo, tên, value proposition.
Dùng badge để giảm chữ nhưng tăng độ tin cậy.
Tạo thanh điều hướng nhanh bằng anchor links.
Ưu tiên “experience narrative” trước “implementation detail”.
Nhóm nội dung theo câu hỏi người đọc, không theo cấu trúc code.
Dùng block song song (2 cột) để tăng nhịp đọc.
Mỗi section chỉ nên có 1 mục tiêu truyền thông chính.
Tránh tường chữ, tối đa hóa scanability (bullet ngắn, spacing thoáng).
Đưa quick start lên sớm để giảm friction.
Giữ quick start “1 lệnh nếu có thể”.
Luôn có phần runtime proof (đã test thật).
Trình bày flow bằng pipeline line để người đọc nhìn phát hiểu ngay.
Show output journey để người xem hình dung đầu ra thực tế.
Tách API theo domain hành vi (pipeline / operations / download).
Dùng ngôn ngữ hành động (Run, Clear, Download, Orchestrate).
Có roadmap 3 phase để thể hiện chiến lược phát triển.
README tập trung “what + why”, docs tập trung “how”.
Link docs rõ ràng để chuyển tầng thông tin.
Đảm bảo visual assets tồn tại thật (tránh link gãy).
Nhất quán phong cách thị giác: badge style, icon style, spacing.
Tối ưu cho cả desktop và mobile reading trên GitHub.
Dùng markdown thuần, hạn chế hack HTML phức tạp.
Tránh nested list quá sâu vì khó scan.
Mọi thuật ngữ quan trọng nên có ngữ cảnh ngắn đi kèm.
Giữ tone chuyên nghiệp, tự tin, không phô trương.
Mỗi mục nên có “user value” rõ hơn “internal technicality”.
Tránh lặp thông tin giữa nhiều section.
Đưa trạng thái version rõ ràng để người đọc biết maturity.
Ghi rõ license để tránh mơ hồ pháp lý.
Nếu có UI, luôn nên có phần “experience” hoặc “snapshot”.
“Before/After” là mẫu kể chuyện mạnh cho pipeline project.
Đặt tên section theo lợi ích (Experience, Output Journey) thay vì generic.
Ưu tiên readability hơn decoration.
Đảm bảo readme vẫn hữu ích khi ảnh không load.
Cân bằng giữa branding và tính thực dụng.
Chuẩn hóa cụm từ xuyên suốt để giữ nhận diện.
Kết thúc README bằng “next confidence signals” (roadmap/version).
Luôn cập nhật README cùng lúc khi thay đổi UX/API chính.