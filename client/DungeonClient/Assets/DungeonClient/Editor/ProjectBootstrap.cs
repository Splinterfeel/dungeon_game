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
        private const string UiDocumentPath = UiFolder + "/PilotSelection.uxml";
        private const string UiStylePath = UiFolder + "/PilotSelection.uss";
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
            var document = app.AddComponent<UIDocument>();
            document.panelSettings = GetOrCreatePanelSettings();
            document.visualTreeAsset = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(UiDocumentPath);
            var pilotSelection = app.AddComponent<PilotSelectionScreen>();
            pilotSelection.SetStyleSheet(AssetDatabase.LoadAssetAtPath<StyleSheet>(UiStylePath));

            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[]
            {
                new EditorBuildSettingsScene(ScenePath, true),
            };
            AssetDatabase.SaveAssets();
            Debug.Log("Стартовая сцена DungeonClient создана.");
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
