using DungeonClient.App;
using DungeonClient.Screens;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UIElements;

namespace DungeonClient.Editor
{
    /// <summary>
    /// Одна и та же команда используется из меню редактора и Unity CLI.
    /// </summary>
    public static class ProjectBootstrap
    {
        private const string SceneFolder = "Assets/DungeonClient/Scenes";
        private const string ScenePath = SceneFolder + "/Bootstrap.unity";
        private const string UiFolder = "Assets/DungeonClient/UI";
        private const string PilotDocumentPath = UiFolder + "/PilotSelection.uxml";
        private const string PilotStylePath = UiFolder + "/PilotSelection.uss";
        private const string GarageDocumentPath = UiFolder + "/Garage.uxml";
        private const string GarageStylePath = UiFolder + "/Garage.uss";
        private const string PilotHubDocumentPath = UiFolder + "/PilotHub.uxml";
        private const string PilotHubStylePath = UiFolder + "/PilotHub.uss";
        private const string PanelSettingsPath = UiFolder + "/DungeonPanelSettings.asset";

        [MenuItem("Dungeon Client/Создать стартовую сцену")]
        public static void CreateBaseScene()
        {
            EnsureFolder("Assets/DungeonClient");
            EnsureFolder(SceneFolder);
            EnsureFolder(UiFolder);

            var scene = EditorSceneManager.NewScene(
                NewSceneSetup.EmptyScene,
                NewSceneMode.Single
            );
            CreateCamera();
            CreateLight();

            var app = new GameObject("DungeonClient");
            app.AddComponent<ClientApp>();
            var panelSettings = GetOrCreatePanelSettings();
            CreatePilotScreen(app.transform, panelSettings);
            CreatePilotHubScreen(app.transform, panelSettings);
            CreateGarageScreen(app.transform, panelSettings);

            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[]
            {
                new EditorBuildSettingsScene(ScenePath, true),
            };
            AssetDatabase.SaveAssets();
            Debug.Log("Стартовая сцена DungeonClient создана.");
        }

        [MenuItem("Dungeon Client/Добавить экран маршрута пилота")]
        public static void AddPilotHubToOpenScene()
        {
            if (Object.FindFirstObjectByType<PilotHubScreen>() != null)
            {
                Debug.Log("Экран маршрута пилота уже есть в сцене.");
                return;
            }

            var app = Object.FindFirstObjectByType<ClientApp>();
            var pilotScreen = Object.FindFirstObjectByType<PilotSelectionScreen>();
            if (app == null || pilotScreen == null)
            {
                throw new System.InvalidOperationException(
                    "В открытой сцене нет стартового объекта DungeonClient"
                );
            }

            var panelSettings = pilotScreen.GetComponent<UIDocument>().panelSettings;
            if (panelSettings == null)
            {
                throw new System.InvalidOperationException("Не настроена панель UI Toolkit");
            }

            CreatePilotHubScreen(app.transform, panelSettings);
            EditorSceneManager.MarkSceneDirty(app.gameObject.scene);
            EditorSceneManager.SaveScene(app.gameObject.scene);
            Debug.Log("Экран маршрута пилота добавлен в сцену.");
        }

        private static void CreatePilotScreen(Transform parent, PanelSettings panelSettings)
        {
            var screen = new GameObject("PilotSelectionScreen");
            screen.transform.SetParent(parent, false);
            var document = screen.AddComponent<UIDocument>();
            document.panelSettings = panelSettings;
            document.visualTreeAsset = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(
                PilotDocumentPath
            );
            var controller = screen.AddComponent<PilotSelectionScreen>();
            controller.SetStyleSheet(AssetDatabase.LoadAssetAtPath<StyleSheet>(PilotStylePath));
        }

        private static void CreateGarageScreen(Transform parent, PanelSettings panelSettings)
        {
            var screen = new GameObject("GarageScreen");
            screen.transform.SetParent(parent, false);
            var document = screen.AddComponent<UIDocument>();
            document.panelSettings = panelSettings;
            document.visualTreeAsset = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(
                GarageDocumentPath
            );
            var controller = screen.AddComponent<GarageScreen>();
            controller.SetStyleSheet(AssetDatabase.LoadAssetAtPath<StyleSheet>(GarageStylePath));
        }

        private static void CreatePilotHubScreen(Transform parent, PanelSettings panelSettings)
        {
            var screen = new GameObject("PilotHubScreen");
            screen.transform.SetParent(parent, false);
            var document = screen.AddComponent<UIDocument>();
            document.panelSettings = panelSettings;
            document.visualTreeAsset = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(
                PilotHubDocumentPath
            );
            var controller = screen.AddComponent<PilotHubScreen>();
            controller.SetStyleSheet(AssetDatabase.LoadAssetAtPath<StyleSheet>(PilotHubStylePath));
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path))
            {
                return;
            }

            var parent = System.IO.Path.GetDirectoryName(path)?.Replace("\\", "/");
            var folderName = System.IO.Path.GetFileName(path);
            if (string.IsNullOrEmpty(parent) || string.IsNullOrEmpty(folderName))
            {
                throw new System.InvalidOperationException($"Не удалось создать папку {path}");
            }

            AssetDatabase.CreateFolder(parent, folderName);
        }

        private static void CreateCamera()
        {
            var cameraObject = new GameObject("Main Camera");
            cameraObject.tag = "MainCamera";
            cameraObject.transform.position = new Vector3(0f, 8f, -8f);
            cameraObject.transform.rotation = Quaternion.Euler(35f, 0f, 0f);

            var camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.04f, 0.06f, 0.09f);
        }

        private static void CreateLight()
        {
            var lightObject = new GameObject("Directional Light");
            lightObject.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            var light = lightObject.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.2f;
        }

        private static PanelSettings GetOrCreatePanelSettings()
        {
            var panelSettings = AssetDatabase.LoadAssetAtPath<PanelSettings>(PanelSettingsPath);
            if (panelSettings != null)
            {
                return panelSettings;
            }

            panelSettings = ScriptableObject.CreateInstance<PanelSettings>();
            AssetDatabase.CreateAsset(panelSettings, PanelSettingsPath);
            return panelSettings;
        }
    }
}
