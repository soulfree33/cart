# Windows 바이너리 빌드

Python이 설치된 Windows 빌드 PC에서 아래 명령을 실행합니다.

```bat
python -m pip install -r requirements-build.txt
build_windows.bat
```

배포 파일은 `dist\KartBoardGame-Windows.zip`입니다. ZIP을 압축 해제한 뒤
`KartBoardGame\KartBoardGame.exe`를 실행하세요. EXE만 따로 옮기지 말고
압축 해제된 폴더 전체를 함께 배포해야 합니다.

빌드에는 게임 이미지와 맵, 카드 정의가 포함됩니다. `chat.json`은 게임 실행에
사용되지 않으므로 배포 파일에서 제외됩니다.
